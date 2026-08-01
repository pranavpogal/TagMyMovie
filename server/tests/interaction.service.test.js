import assert from "node:assert/strict";
import test from "node:test";
import mongoose from "mongoose";
import {
  buildDeduplicationFilter,
  frontendEventSources,
  frontendEventTypes,
  InteractionValidationError,
  normalizeInteraction,
  recordInteraction,
  sanitizeInteractionMetadata,
} from "../src/services/interaction.service.js";

const userId = new mongoose.Types.ObjectId().toString();

const validInteraction = (overrides = {}) => ({
  userId,
  mediaId: 603,
  mediaType: "movie",
  eventType: "detail_view",
  source: "media_detail",
  sessionId: "session-1",
  ...overrides,
});

test("normalizes media identity and default values", () => {
  const result = normalizeInteraction(validInteraction());

  assert.equal(result.user, userId);
  assert.equal(result.mediaId, "603");
  assert.equal(result.mediaType, "movie");
  assert.equal(result.value, 1);
  assert.deepEqual(result.metadata, {});
});

test("rejects invalid event and media types", () => {
  assert.throws(
    () => normalizeInteraction(validInteraction({ eventType: "custom_event" })),
    InteractionValidationError
  );
  assert.throws(
    () => normalizeInteraction(validInteraction({ mediaType: "person" })),
    InteractionValidationError
  );
});

test("sanitizes metadata and rejects injection-shaped or nested values", () => {
  assert.deepEqual(
    sanitizeInteractionMetadata({ context: "search", genres: [12, 18] }),
    { context: "search", genres: [12, 18] }
  );
  assert.throws(
    () => sanitizeInteractionMetadata({ "$set": "unsafe" }),
    InteractionValidationError
  );
  assert.throws(
    () => sanitizeInteractionMetadata({ nested: { private: true } }),
    InteractionValidationError
  );
});

test("uses a session-scoped time window for detail views", () => {
  const now = new Date("2026-08-01T12:00:00.000Z");
  const interaction = normalizeInteraction(validInteraction());
  const filter = buildDeduplicationFilter(interaction, now);

  assert.equal(filter.sessionId, "session-1");
  assert.equal(filter.mediaId, "603");
  assert.equal(
    filter.createdAt.$gte.toISOString(),
    "2026-08-01T11:45:00.000Z"
  );
});

test("deduplicates recommendation clicks by batch and compound item identity", () => {
  const interaction = normalizeInteraction(
    validInteraction({
      eventType: "recommendation_click",
      recommendationId: "batch-1",
    })
  );
  const filter = buildDeduplicationFilter(interaction);

  assert.equal(filter.recommendationId, "batch-1");
  assert.equal(filter.mediaType, "movie");
  assert.equal(filter.mediaId, "603");
  assert.equal(filter.createdAt, undefined);
});

test("stateful events are never time-window deduplicated", () => {
  const interaction = normalizeInteraction(
    validInteraction({ eventType: "favourite_add" })
  );

  assert.equal(buildDeduplicationFilter(interaction), null);
});

test("recordInteraction skips a duplicate and does not insert it", async () => {
  let createCalled = false;
  const existing = { id: "existing-interaction" };
  const model = {
    findOne: async () => existing,
    create: async () => {
      createCalled = true;
    },
  };

  const result = await recordInteraction(validInteraction(), { model });

  assert.equal(result.recorded, false);
  assert.equal(result.deduplicated, true);
  assert.equal(result.interaction, existing);
  assert.equal(createCalled, false);
});

test("browser event allowlist excludes trusted state changes", () => {
  assert.deepEqual(frontendEventTypes, [
    "search_click",
    "recommendation_click",
    "trailer_play",
    "detail_view",
  ]);
  assert.equal(frontendEventTypes.includes("favourite_add"), false);
  assert.equal(frontendEventTypes.includes("rating_submit"), false);
  assert.deepEqual(frontendEventSources, {
    search_click: "search",
    recommendation_click: "recommendation",
    trailer_play: "media_detail",
    detail_view: "media_detail",
  });
});
