import assert from "node:assert/strict";
import test from "node:test";
import {
  normalizeSemanticSearchQuery,
  SemanticSearchRequestError,
  semanticSearch,
} from "../src/services/semanticSearch.service.js";

const payload = {
  strategy: "content_based",
  generatedAt: "2026-08-02T00:00:00.000Z",
  modelVersions: { embedding: "content-v1", collaborative: null, profile: null, ranking: null, diversity: null },
  collaborativeConfidence: 0,
  results: [{ mediaId: "42", mediaType: "movie", title: "Mystery", posterPath: "/poster.jpg",
    releaseYear: 2020, voteAverage: 8, score: 0.9, sourceModels: ["content"],
    reasons: ["Matches the meaning of your search"] }],
};

test("normalizes semantic filters and rejects unsafe input", () => {
  assert.deepEqual(normalizeSemanticSearchQuery({
    query: "  dark mystery  ", mediaType: "movie", language: "EN",
    genreIds: "18,9648,18", limit: "10",
  }), {
    query: "dark mystery", mediaType: "movie", language: "en",
    genreIds: [18, 9648], limit: 10,
  });
  assert.throws(() => normalizeSemanticSearchQuery({ query: "x", mediaType: "movie" }), SemanticSearchRequestError);
  assert.throws(() => normalizeSemanticSearchQuery({ query: "valid", mediaType: "people" }), SemanticSearchRequestError);
  assert.throws(() => normalizeSemanticSearchQuery({ query: "valid", mediaType: "movie", debug: true }), SemanticSearchRequestError);
  assert.equal(normalizeSemanticSearchQuery({ query: "space adventure" }).mediaType, null);
});

test("returns validated normal media-card metadata from ML", async () => {
  let received;
  const response = await semanticSearch(
    { query: "dark mystery", mediaType: "movie", genreIds: "9648" },
    { mlClient: { semanticSearch: async (params) => { received = params; return payload; } } }
  );
  assert.equal(received.genreIds[0], 9648);
  assert.equal(response.searchType, "semantic");
  assert.equal(response.results[0].posterPath, "/poster.jpg");
});
