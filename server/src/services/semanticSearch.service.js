import mlServiceClient from "../clients/mlService.client.js";
import { validateMlRecommendationResponse } from "./recommendation.service.js";

export class SemanticSearchRequestError extends Error {
  constructor(message) {
    super(message);
    this.name = "SemanticSearchRequestError";
  }
}

const allowedFields = new Set(["query", "mediaType", "language", "genreIds", "limit"]);

export const normalizeSemanticSearchQuery = (query = {}) => {
  if (Object.keys(query).some((field) => !allowedFields.has(field))) {
    throw new SemanticSearchRequestError("query contains unsupported parameters");
  }
  const text = query.query?.toString().trim();
  const mediaType = query.mediaType?.toString().trim() || null;
  const language = query.language?.toString().trim().toLowerCase() || null;
  const limit = Number(query.limit || 20);
  const rawGenres = query.genreIds === undefined
    ? []
    : Array.isArray(query.genreIds) ? query.genreIds : query.genreIds.toString().split(",");
  const genreIds = [...new Set(rawGenres.map(Number))];
  if (!text || text.length < 2 || text.length > 500) {
    throw new SemanticSearchRequestError("query must contain between 2 and 500 characters");
  }
  if (mediaType && !['movie', 'tv'].includes(mediaType)) {
    throw new SemanticSearchRequestError("mediaType must be movie or tv");
  }
  if (language && !/^[a-z]{2,3}$/.test(language)) {
    throw new SemanticSearchRequestError("language is invalid");
  }
  if (!Number.isInteger(limit) || limit < 1 || limit > 50) {
    throw new SemanticSearchRequestError("limit must be between 1 and 50");
  }
  if (genreIds.length > 20 || genreIds.some((id) => !Number.isInteger(id) || id <= 0)) {
    throw new SemanticSearchRequestError("genreIds is invalid");
  }
  return { query: text, mediaType, language, genreIds, limit };
};

export const semanticSearch = async (query, dependencies = {}) => {
  const params = normalizeSemanticSearchQuery(query);
  const client = dependencies.mlClient || mlServiceClient;
  const response = validateMlRecommendationResponse(
    await client.semanticSearch(params),
    params.limit
  );
  return {
    query: params.query,
    searchType: "semantic",
    strategy: response.strategy,
    modelVersions: response.modelVersions,
    results: response.results,
  };
};

export default { semanticSearch };
