import mediaCatalogModel from "../models/mediaCatalog.model.js";
import userPreferenceModel from "../models/userPreference.model.js";
import tmdbApi from "../tmdb/tmdb.api.js";
import mlServiceClient from "../clients/mlService.client.js";
import { recordRecommendationImpression } from "./recommendationImpression.service.js";

const mediaTypes = ["movie", "tv"];
const contexts = ["home", "media_detail", "other"];
const allowedQueryFields = new Set([
  "mediaType", "limit", "context", "seedMediaId", "seedMediaType", "excludeSeen",
]);

export class RecommendationRequestError extends Error {
  constructor(message) {
    super(message);
    this.name = "RecommendationRequestError";
  }
}

export const normalizeRecommendationQuery = (query = {}) => {
  if (Object.keys(query).some((field) => !allowedQueryFields.has(field))) {
    throw new RecommendationRequestError("query contains unsupported parameters");
  }
  const mediaType = query.mediaType || "movie";
  const context = query.context || "home";
  const limit = Number(query.limit || 20);
  const seedMediaId = query.seedMediaId?.toString().trim() || null;
  const seedMediaType = query.seedMediaType || null;
  if (!mediaTypes.includes(mediaType) || !contexts.includes(context)) {
    throw new RecommendationRequestError("mediaType or context is invalid");
  }
  if (!Number.isInteger(limit) || limit < 1 || limit > 50) {
    throw new RecommendationRequestError("limit must be between 1 and 50");
  }
  if (seedMediaType !== null && !mediaTypes.includes(seedMediaType)) {
    throw new RecommendationRequestError("seedMediaType is invalid");
  }
  if ((seedMediaId === null) !== (seedMediaType === null)) {
    throw new RecommendationRequestError("seedMediaId and seedMediaType must be supplied together");
  }
  if (seedMediaId && seedMediaId.length > 64) {
    throw new RecommendationRequestError("seedMediaId is invalid");
  }
  let excludeSeen = true;
  if (query.excludeSeen !== undefined) {
    if (!['true', 'false', true, false].includes(query.excludeSeen)) {
      throw new RecommendationRequestError("excludeSeen is invalid");
    }
    excludeSeen = query.excludeSeen === true || query.excludeSeen === "true";
  }
  return { mediaType, limit, context, seedMediaId, seedMediaType, excludeSeen };
};

export const validateMlRecommendationResponse = (payload, limit = 50) => {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new RecommendationRequestError("ML response is invalid");
  }
  if (typeof payload.strategy !== "string" || !payload.strategy.trim()) {
    throw new RecommendationRequestError("ML strategy is invalid");
  }
  if (!Array.isArray(payload.results) || payload.results.length > limit) {
    throw new RecommendationRequestError("ML results are invalid");
  }
  const seen = new Set();
  const results = payload.results.map((item) => {
    const mediaId = item?.mediaId?.toString().trim();
    if (!mediaId || !mediaTypes.includes(item?.mediaType)) {
      throw new RecommendationRequestError("ML result identity is invalid");
    }
    const key = `${item.mediaType}:${mediaId}`;
    if (seen.has(key)) throw new RecommendationRequestError("ML results contain duplicates");
    seen.add(key);
    const score = Number(item.score);
    if (!Number.isFinite(score) || score < 0 || score > 1) {
      throw new RecommendationRequestError("ML result score is invalid");
    }
    if (!Array.isArray(item.sourceModels) || !Array.isArray(item.reasons) ||
        item.sourceModels.length > 10 || item.reasons.length > 3 ||
        item.sourceModels.some((value) => typeof value !== "string" || !value.trim() || value.length > 64) ||
        item.reasons.some((value) => typeof value !== "string" || !value.trim() || value.length > 300)) {
      throw new RecommendationRequestError("ML result evidence is invalid");
    }
    return {
      mediaId, mediaType: item.mediaType, title: String(item.title || ""),
      posterPath: String(item.posterPath || ""), releaseYear: item.releaseYear ?? null,
      voteAverage: Number(item.voteAverage || 0), score,
      sourceModels: item.sourceModels.map(String), reasons: item.reasons.map(String),
    };
  });
  const versions = payload.modelVersions;
  if (!versions || typeof versions !== "object" || Array.isArray(versions)) {
    throw new RecommendationRequestError("ML modelVersions are invalid");
  }
  const versionFields = ["embedding", "collaborative", "profile", "ranking", "diversity"];
  if (Object.keys(versions).some((field) => !versionFields.includes(field)) ||
      Object.values(versions).some((value) => value !== null &&
        (typeof value !== "string" || !value.trim() || value.length > 100))) {
    throw new RecommendationRequestError("ML modelVersions are invalid");
  }
  const confidence = Number(payload.collaborativeConfidence || 0);
  if (!Number.isFinite(confidence) || confidence < 0 || confidence > 1) {
    throw new RecommendationRequestError("ML collaborative confidence is invalid");
  }
  return {
    strategy: payload.strategy.trim(), modelVersions: versions,
    collaborativeConfidence: confidence,
    generatedAt: Number.isNaN(Date.parse(payload.generatedAt)) ? null : payload.generatedAt,
    results,
  };
};

const mapTmdb = (item, mediaType, reason) => ({
  mediaId: String(item.id), mediaType, title: item.title || item.name || "",
  posterPath: item.poster_path || "", releaseYear: Number((item.release_date || item.first_air_date || "").slice(0, 4)) || null,
  voteAverage: Number(item.vote_average || 0), score: 0,
  sourceModels: ["tmdb"], reasons: [reason],
});

export const resolveRecommendationFallback = async (userId, params, dependencies = {}) => {
  const tmdb = dependencies.tmdb || tmdbApi;
  const preferences = dependencies.preferenceModel || userPreferenceModel;
  const catalogue = dependencies.catalogueModel || mediaCatalogModel;
  if (params.seedMediaId) {
    try {
      const response = await tmdb.mediaRecommend({ mediaType: params.seedMediaType, mediaId: params.seedMediaId });
      const results = (response.results || []).slice(0, params.limit).map(
        (item) => mapTmdb(item, params.seedMediaType, "Similar to this title")
      );
      if (results.length) return { strategy: "tmdb_fallback", modelVersions: {}, collaborativeConfidence: 0, results };
    } catch {}
  }
  const preference = await preferences.findOne({ user: userId }).lean().catch(() => null);
  if (preference && ((preference.preferredGenreIds || []).length || (preference.preferredLanguages || []).length)) {
    const filters = { mediaType: params.mediaType };
    if (preference.preferredGenreIds?.length) filters.genreIds = { $in: preference.preferredGenreIds };
    if (preference.preferredLanguages?.length) filters.originalLanguage = { $in: preference.preferredLanguages };
    const docs = await catalogue.find(filters).sort({ popularity: -1, voteAverage: -1 }).limit(params.limit).lean().catch(() => []);
    if (docs.length) return { strategy: "onboarding_preferences", modelVersions: {}, collaborativeConfidence: 0,
      results: docs.map((item) => ({ mediaId: item.tmdbId, mediaType: item.mediaType, title: item.title,
        posterPath: item.posterPath || "", releaseYear: item.releaseYear, voteAverage: item.voteAverage,
        score: 0, sourceModels: ["preferences"], reasons: ["Matches your selected preferences"] })) };
  }
  const docs = await catalogue.find({ mediaType: params.mediaType }).sort({ popularity: -1, voteAverage: -1 }).limit(params.limit).lean().catch(() => []);
  if (docs.length) return { strategy: "cold_start_popular", modelVersions: {}, collaborativeConfidence: 0,
    results: docs.map((item) => ({ mediaId: item.tmdbId, mediaType: item.mediaType, title: item.title,
      posterPath: item.posterPath || "", releaseYear: item.releaseYear, voteAverage: item.voteAverage,
      score: 0, sourceModels: ["popularity"], reasons: ["Popular and well-rated"] })) };
  const response = await tmdb.mediaList({ mediaType: params.mediaType, mediaCategory: "popular", page: 1 });
  return { strategy: "tmdb_fallback", modelVersions: {}, collaborativeConfidence: 0,
    results: (response.results || []).slice(0, params.limit).map(
      (item) => mapTmdb(item, params.mediaType, "Popular on TMDB")
    ) };
};

export const getRecommendations = async (input, dependencies = {}) => {
  const params = normalizeRecommendationQuery(input.query);
  const client = dependencies.mlClient || mlServiceClient;
  const fallback = dependencies.fallbackResolver || resolveRecommendationFallback;
  const recorder = dependencies.impressionRecorder || recordRecommendationImpression;
  let response;
  try {
    response = validateMlRecommendationResponse(
      await client.recommendations(input.userId.toString(), params), params.limit
    );
    if (!response.results.length) throw new RecommendationRequestError("ML response is empty");
  } catch (error) {
    console.warn("ML recommendation fallback", { errorName: error?.name });
    response = await fallback(input.userId.toString(), params, dependencies);
  }
  let recommendationId = null;
  if (response.results.length) {
    const impression = await recorder({
      userId: input.userId, context: { page: params.context, mediaType: params.mediaType,
        seedMediaId: params.seedMediaId, seedMediaType: params.seedMediaType },
      strategy: response.strategy, modelVersions: response.modelVersions,
      items: response.results.map((item, index) => ({ mediaId: item.mediaId, mediaType: item.mediaType,
        rank: index + 1, finalScore: item.score, sourceModels: item.sourceModels })),
    });
    recommendationId = impression.recommendationId;
  }
  return {
    recommendationId,
    ...response,
    generatedAt: response.generatedAt || new Date().toISOString(),
  };
};

export default { getRecommendations };
