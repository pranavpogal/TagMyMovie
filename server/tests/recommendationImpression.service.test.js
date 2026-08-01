import assert from "node:assert/strict";
import test from "node:test";
import mongoose from "mongoose";
import recommendationImpressionModel from "../src/models/recommendationImpression.model.js";
import {
  normalizeRecommendationImpression,
  RecommendationImpressionValidationError,
  recordRecommendationImpression,
} from "../src/services/recommendationImpression.service.js";

const userId = new mongoose.Types.ObjectId().toString();

const validImpression = (overrides = {}) => ({
  userId,
  context: {
    page: "media_detail",
    mediaType: "movie",
    seedMediaId: "550",
    seedMediaType: "movie",
  },
  strategy: "tmdb_fallback",
  modelVersions: {},
  items: [
    {
      mediaId: 603,
      mediaType: "movie",
      rank: 1,
      finalScore: null,
      sourceModels: ["tmdb"],
    },
  ],
  ...overrides,
});

test("normalizes an impression without fabricating scores or model versions", () => {
  const normalized = normalizeRecommendationImpression(validImpression());

  assert.equal(normalized.user, userId);
  assert.equal(normalized.items[0].mediaId, "603");
  assert.equal(normalized.items[0].finalScore, null);
  assert.deepEqual(normalized.items[0].sourceModels, ["tmdb"]);
  assert.deepEqual(normalized.modelVersions, {
    embedding: null,
    collaborative: null,
    profile: null,
    ranking: null,
    diversity: null,
  });
});

test("requires compound seed identity and valid item media types", () => {
  assert.throws(
    () =>
      normalizeRecommendationImpression(
        validImpression({
          context: {
            page: "media_detail",
            mediaType: "movie",
            seedMediaId: "550",
          },
        })
      ),
    RecommendationImpressionValidationError
  );
  assert.throws(
    () =>
      normalizeRecommendationImpression(
        validImpression({
          items: [{ mediaId: "1", mediaType: "person", rank: 1 }],
        })
      ),
    RecommendationImpressionValidationError
  );
});

test("rejects duplicate compound items and invalid source model payloads", () => {
  const item = { mediaId: "603", mediaType: "movie", rank: 1 };
  assert.throws(
    () =>
      normalizeRecommendationImpression(
        validImpression({ items: [item, { ...item, rank: 2 }] })
      ),
    RecommendationImpressionValidationError
  );
  assert.throws(
    () =>
      normalizeRecommendationImpression(
        validImpression({ items: [{ ...item, sourceModels: "tmdb" }] })
      ),
    RecommendationImpressionValidationError
  );
});

test("records one generated recommendation ID with normalized items", async () => {
  let inserted;
  const model = {
    create: async (document) => {
      inserted = document;
      return { id: "mongo-id", ...document };
    },
  };

  const result = await recordRecommendationImpression(validImpression(), {
    model,
    idFactory: () => "recommendation-batch-1",
  });

  assert.equal(result.recommendationId, "recommendation-batch-1");
  assert.equal(inserted.recommendationId, "recommendation-batch-1");
  assert.equal(inserted.items[0].rank, 1);
  assert.equal(inserted.items[0].mediaId, "603");
});

test("schema defines unique recommendation ID and TTL retention indexes", () => {
  const indexes = recommendationImpressionModel.schema.indexes();
  const recommendationIdIndex = indexes.find(
    ([fields]) => fields.recommendationId === 1
  );
  const ttlIndex = indexes.find(([, options]) => options.expireAfterSeconds);

  assert.equal(recommendationIdIndex[1].unique, true);
  assert.ok(ttlIndex[1].expireAfterSeconds > 0);
});
