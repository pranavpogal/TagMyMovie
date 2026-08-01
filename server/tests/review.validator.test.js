import assert from "node:assert/strict";
import test from "node:test";
import {
  normalizeReviewPayload,
  normalizeReviewRating,
  ReviewValidationError,
  validateFinalReview,
} from "../src/validators/review.validator.js";

test("accepts review text without a rating", () => {
  assert.deepEqual(normalizeReviewPayload({ content: "  Great film  " }), {
    content: "Great film",
    rating: undefined,
  });
});

test("accepts a rating-only review", () => {
  assert.deepEqual(normalizeReviewPayload({ rating: 8.5 }), {
    content: undefined,
    rating: 8.5,
  });
});

test("accepts only half-point ratings from one to ten", () => {
  for (const rating of [1, 1.5, 5, 9.5, 10]) {
    assert.equal(normalizeReviewRating(rating), rating);
  }
  for (const rating of [0.5, 4.2, 10.5, "invalid"]) {
    assert.throws(() => normalizeReviewRating(rating), ReviewValidationError);
  }
});

test("rejects empty review creation", () => {
  assert.throws(
    () => normalizeReviewPayload({ content: "", rating: null }),
    ReviewValidationError
  );
});

test("allows partial updates but validates the final review", () => {
  assert.deepEqual(normalizeReviewPayload({ rating: 7 }, { partial: true }), {
    content: undefined,
    rating: 7,
  });
  assert.throws(
    () => normalizeReviewPayload({}, { partial: true }),
    ReviewValidationError
  );
  assert.throws(
    () => validateFinalReview({ content: "", rating: null }),
    ReviewValidationError
  );
});
