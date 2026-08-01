import assert from "node:assert/strict";
import test from "node:test";
import {
  normalizePreferencePayload,
  PreferenceValidationError,
} from "../src/validators/preference.validator.js";

test("normalizes and deduplicates genre and language preferences", () => {
  assert.deepEqual(
    normalizePreferencePayload({
      preferredGenreIds: [28, "28", 12],
      preferredLanguages: ["EN", "kn", "en"],
    }),
    {
      preferredGenreIds: [28, 12],
      preferredLanguages: ["en", "kn"],
    }
  );
});

test("normalizes seed media with compound movie and TV identity", () => {
  assert.deepEqual(
    normalizePreferencePayload({
      favouriteSeedMedia: [
        {
          mediaId: 603,
          mediaType: "movie",
          title: "The Matrix",
          posterPath: "/poster.jpg",
        },
        {
          mediaId: 603,
          mediaType: "tv",
          title: "A TV title",
          posterPath: "",
        },
      ],
    }).favouriteSeedMedia.map(({ mediaId, mediaType }) => ({ mediaId, mediaType })),
    [
      { mediaId: "603", mediaType: "movie" },
      { mediaId: "603", mediaType: "tv" },
    ]
  );
});

test("rejects duplicate seed media and unknown fields", () => {
  const seed = {
    mediaId: "603",
    mediaType: "movie",
    title: "The Matrix",
    posterPath: "",
  };
  assert.throws(
    () => normalizePreferencePayload({ favouriteSeedMedia: [seed, seed] }),
    PreferenceValidationError
  );
  assert.throws(
    () => normalizePreferencePayload({ user: "not-allowed" }),
    PreferenceValidationError
  );
});

test("completed and skipped onboarding states are mutually exclusive", () => {
  assert.deepEqual(normalizePreferencePayload({ onboardingCompleted: true }), {
    onboardingCompleted: true,
    onboardingSkipped: false,
  });
  assert.deepEqual(normalizePreferencePayload({ onboardingSkipped: true }), {
    onboardingSkipped: true,
    onboardingCompleted: false,
  });
});

test("rejects malformed preference arrays", () => {
  assert.throws(
    () => normalizePreferencePayload({ preferredLanguages: ["english"] }),
    PreferenceValidationError
  );
  assert.throws(
    () => normalizePreferencePayload({ preferredGenreIds: [-1] }),
    PreferenceValidationError
  );
});
