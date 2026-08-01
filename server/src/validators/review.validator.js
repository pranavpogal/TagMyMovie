export class ReviewValidationError extends Error {
  constructor(message) {
    super(message);
    this.name = "ReviewValidationError";
  }
}

export const normalizeReviewContent = (content) => {
  if (content === undefined || content === null) return "";
  if (typeof content !== "string") {
    throw new ReviewValidationError("content must be a string");
  }

  const normalized = content.trim();
  if (normalized.length > 2000) {
    throw new ReviewValidationError("content must be at most 2000 characters");
  }
  return normalized;
};

export const normalizeReviewRating = (rating) => {
  if (rating === undefined || rating === null || rating === "") return null;

  const normalized = Number(rating);
  if (
    !Number.isFinite(normalized) ||
    normalized < 1 ||
    normalized > 10 ||
    !Number.isInteger(normalized * 2)
  ) {
    throw new ReviewValidationError(
      "rating must be between 1 and 10 in half-point steps"
    );
  }
  return normalized;
};

export const normalizeReviewPayload = (payload, options = {}) => {
  const partial = options.partial === true;
  const hasContent = Object.prototype.hasOwnProperty.call(payload, "content");
  const hasRating = Object.prototype.hasOwnProperty.call(payload, "rating");

  if (partial && !hasContent && !hasRating) {
    throw new ReviewValidationError("content or rating is required");
  }

  const content = hasContent ? normalizeReviewContent(payload.content) : undefined;
  const rating = hasRating ? normalizeReviewRating(payload.rating) : undefined;

  if (!partial && !content && rating === null) {
    throw new ReviewValidationError("content or rating is required");
  }

  return { content, rating };
};

export const validateFinalReview = ({ content, rating }) => {
  if (!normalizeReviewContent(content) && normalizeReviewRating(rating) === null) {
    throw new ReviewValidationError("content or rating is required");
  }
};
