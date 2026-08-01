import assert from "node:assert/strict";
import test from "node:test";
import mediaCatalogModel from "../src/models/mediaCatalog.model.js";

const validMedia = (overrides = {}) => ({
  tmdbId: "603",
  mediaType: "movie",
  title: "The Matrix",
  originalTitle: "The Matrix",
  overview: "A computer hacker learns the nature of reality.",
  genres: [
    { id: 28, name: "Action" },
    { id: 878, name: "Science Fiction" },
  ],
  genreIds: [28, 878],
  originalLanguage: "en",
  spokenLanguages: ["en"],
  releaseDate: new Date("1999-03-30T00:00:00.000Z"),
  releaseYear: 1999,
  cast: ["Keanu Reeves"],
  directors: ["Lana Wachowski", "Lilly Wachowski"],
  creators: [],
  keywords: ["simulation", "artificial reality"],
  popularity: 100,
  voteAverage: 8.2,
  voteCount: 25000,
  posterPath: "/poster.jpg",
  backdropPath: "/backdrop.jpg",
  featureText: "",
  featureHash: "",
  embedding: [],
  embeddingDimension: 0,
  embeddingModel: null,
  embeddingVersion: null,
  lastSyncedAt: new Date(),
  ...overrides,
});

test("validates normalized movie and TV documents independently", async () => {
  const movie = new mediaCatalogModel(validMedia());
  const tv = new mediaCatalogModel(
    validMedia({ mediaType: "tv", title: "A TV title" })
  );

  await movie.validate();
  await tv.validate();
  assert.equal(movie.tmdbId, tv.tmdbId);
  assert.notEqual(movie.mediaType, tv.mediaType);
});

test("requires the core catalogue identity and metadata", async () => {
  await assert.rejects(
    new mediaCatalogModel(validMedia({ tmdbId: "" })).validate(),
    /tmdbId/
  );
  await assert.rejects(
    new mediaCatalogModel(validMedia({ title: "" })).validate(),
    /title/
  );
  await assert.rejects(
    new mediaCatalogModel(validMedia({ mediaType: "person" })).validate(),
    /mediaType/
  );
});

test("rejects duplicate or invalid normalized genre IDs", async () => {
  await assert.rejects(
    new mediaCatalogModel(validMedia({ genreIds: [28, 28] })).validate(),
    /unique positive integers/
  );
  await assert.rejects(
    new mediaCatalogModel(validMedia({ genreIds: [0] })).validate(),
    /unique positive integers/
  );
});

test("validates embedding dimensions, values, model, and version", async () => {
  await new mediaCatalogModel(
    validMedia({
      embedding: [0.1, 0.2, 0.3],
      embeddingDimension: 3,
      embeddingModel: "sentence-transformers/all-MiniLM-L6-v2",
      embeddingVersion: "content-embedding-v1",
    })
  ).validate();

  await assert.rejects(
    new mediaCatalogModel(
      validMedia({
        embedding: [0.1, 0.2],
        embeddingDimension: 3,
        embeddingModel: "model",
        embeddingVersion: "version",
      })
    ).validate(),
    /embeddingDimension/
  );
  await assert.rejects(
    new mediaCatalogModel(
      validMedia({ embedding: [0.1], embeddingDimension: 1 })
    ).validate(),
    /embeddingModel/
  );
});

test("defines compound uniqueness and all required filter indexes", () => {
  const indexes = mediaCatalogModel.schema.indexes();
  const compoundIdentity = indexes.find(
    ([fields]) => fields.tmdbId === 1 && fields.mediaType === 1
  );

  assert.equal(compoundIdentity[1].unique, true);
  for (const field of [
    "mediaType",
    "genreIds",
    "originalLanguage",
    "releaseYear",
    "voteCount",
  ]) {
    assert.ok(indexes.some(([fields]) => fields[field] === 1));
  }
  assert.equal(mediaCatalogModel.schema.options.collection, "media_catalog");
});
