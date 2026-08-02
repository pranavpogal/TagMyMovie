import assert from "node:assert/strict";
import test from "node:test";
import mongoose from "mongoose";
import {
  RecommendationRequestError,
  getRecommendations,
  normalizeRecommendationQuery,
  validateMlRecommendationResponse,
  resolveRecommendationFallback,
} from "../src/services/recommendation.service.js";

const userId = new mongoose.Types.ObjectId().toString();
const mlPayload = (overrides = {}) => ({
  strategy: "content_based",
  modelVersions: { embedding: "v1", collaborative: null, profile: "p1", ranking: "r1", diversity: "d1" },
  collaborativeConfidence: 0,
  generatedAt: "2026-08-02T00:00:00.000Z",
  results: [{ mediaId: "1", mediaType: "movie", title: "One", score: 0.8,
    sourceModels: ["content"], reasons: ["Recommended from your activity"] }],
  ...overrides,
});

test("normalizes the browser query and rejects arbitrary user/debug parameters", () => {
  assert.deepEqual(normalizeRecommendationQuery({}), {
    mediaType: "movie", limit: 20, context: "home", seedMediaId: null,
    seedMediaType: null, excludeSeen: true,
  });
  assert.throws(() => normalizeRecommendationQuery({ userId: "someone-else" }), RecommendationRequestError);
  assert.throws(() => normalizeRecommendationQuery({ debug: "true" }), RecommendationRequestError);
  assert.throws(() => normalizeRecommendationQuery({ seedMediaId: "1" }), RecommendationRequestError);
  assert.throws(() => normalizeRecommendationQuery({ limit: "51" }), RecommendationRequestError);
});

test("strictly validates ML identities, scores, evidence, confidence and duplicates", () => {
  assert.equal(validateMlRecommendationResponse(mlPayload()).results[0].mediaId, "1");
  assert.throws(() => validateMlRecommendationResponse(mlPayload({ results: [
    mlPayload().results[0], mlPayload().results[0],
  ] })), RecommendationRequestError);
  assert.throws(() => validateMlRecommendationResponse(mlPayload({
    modelVersions: { ...mlPayload().modelVersions, privatePath: "/secret" },
  })), RecommendationRequestError);
  assert.throws(() => validateMlRecommendationResponse(mlPayload({ results: [
    { ...mlPayload().results[0], score: Infinity },
  ] })), RecommendationRequestError);
  assert.throws(() => validateMlRecommendationResponse(mlPayload({ collaborativeConfidence: 2 })), RecommendationRequestError);
  assert.throws(() => validateMlRecommendationResponse(mlPayload({ results: [
    { ...mlPayload().results[0], reasons: ["a", "b", "c", "d"] },
  ] })), RecommendationRequestError);
});

const queryModel = (documents) => ({
  find: () => ({
    sort: () => ({ limit: () => ({ lean: async () => documents }) }),
  }),
});

test("fallback order prefers seed TMDB, then explicit preferences, then popularity", async () => {
  const params = normalizeRecommendationQuery({
    seedMediaId: "42", seedMediaType: "movie", mediaType: "movie", limit: "5",
  });
  let preferenceReads = 0;
  const seed = await resolveRecommendationFallback(userId, params, {
    tmdb: { mediaRecommend: async () => ({ results: [{ id: 9, title: "Seed result" }] }) },
    preferenceModel: { findOne: () => { preferenceReads += 1; return { lean: async () => null }; } },
    catalogueModel: queryModel([]),
  });
  assert.equal(seed.strategy, "tmdb_fallback");
  assert.equal(preferenceReads, 0);

  const preference = await resolveRecommendationFallback(userId, params, {
    tmdb: { mediaRecommend: async () => ({ results: [] }) },
    preferenceModel: { findOne: () => ({ lean: async () => ({ preferredGenreIds: [18] }) }) },
    catalogueModel: queryModel([{ tmdbId: "7", mediaType: "movie", title: "Drama" }]),
  });
  assert.equal(preference.strategy, "onboarding_preferences");

  const popular = await resolveRecommendationFallback(userId, normalizeRecommendationQuery({}), {
    tmdb: { mediaList: async () => ({ results: [] }) },
    preferenceModel: { findOne: () => ({ lean: async () => null }) },
    catalogueModel: queryModel([{ tmdbId: "8", mediaType: "movie", title: "Popular" }]),
  });
  assert.equal(popular.strategy, "cold_start_popular");
});

test("uses authenticated user identity, validates ML, and stores final impression", async () => {
  let calledUser;
  let stored;
  const result = await getRecommendations(
    { userId, query: { mediaType: "movie", context: "home" } },
    {
      mlClient: { recommendations: async (value) => { calledUser = value; return mlPayload(); } },
      impressionRecorder: async (value) => { stored = value; return { recommendationId: "batch-1" }; },
      fallbackResolver: async () => { throw new Error("fallback should not run"); },
    }
  );
  assert.equal(calledUser, userId);
  assert.equal(result.recommendationId, "batch-1");
  assert.equal(stored.userId, userId);
  assert.equal(stored.items[0].finalScore, 0.8);
  assert.equal(stored.strategy, "content_based");
});

test("falls back safely when ML fails or returns an empty result", async () => {
  let fallbackCalls = 0;
  const fallback = async () => {
    fallbackCalls += 1;
    return mlPayload({ strategy: "cold_start_popular" });
  };
  const dependencies = {
    fallbackResolver: fallback,
    impressionRecorder: async () => ({ recommendationId: "fallback-batch" }),
  };
  const failed = await getRecommendations(
    { userId, query: {} },
    { ...dependencies, mlClient: { recommendations: async () => { throw new Error("offline"); } } }
  );
  const empty = await getRecommendations(
    { userId, query: {} },
    { ...dependencies, mlClient: { recommendations: async () => mlPayload({ results: [] }) } }
  );
  assert.equal(failed.strategy, "cold_start_popular");
  assert.equal(empty.recommendationId, "fallback-batch");
  assert.equal(fallbackCalls, 2);
});
