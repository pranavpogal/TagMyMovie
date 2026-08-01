import { randomUUID } from "node:crypto";
import mongoose from "mongoose";
import recommendationImpressionModel from "../models/recommendationImpression.model.js";

const pages = ["home", "media_detail", "other"];
const mediaTypes = ["movie", "tv"];
const modelVersionFields = [
  "embedding",
  "collaborative",
  "profile",
  "ranking",
  "diversity",
];

export class RecommendationImpressionValidationError extends Error {
  constructor(message) {
    super(message);
    this.name = "RecommendationImpressionValidationError";
  }
}

const normalizeOptionalString = (value, field, maxLength) => {
  if (value === undefined || value === null || value === "") return null;
  if (typeof value !== "string") {
    throw new RecommendationImpressionValidationError(`${field} is invalid`);
  }
  const normalized = value.trim();
  if (!normalized || normalized.length > maxLength) {
    throw new RecommendationImpressionValidationError(`${field} is invalid`);
  }
  return normalized;
};

const normalizeContext = (context) => {
  if (!context || typeof context !== "object" || !pages.includes(context.page)) {
    throw new RecommendationImpressionValidationError("context.page is invalid");
  }
  if (!mediaTypes.includes(context.mediaType)) {
    throw new RecommendationImpressionValidationError(
      "context.mediaType is invalid"
    );
  }

  const seedMediaId = normalizeOptionalString(
    context.seedMediaId,
    "context.seedMediaId",
    64
  );
  const seedMediaType = context.seedMediaType || null;
  if (seedMediaType !== null && !mediaTypes.includes(seedMediaType)) {
    throw new RecommendationImpressionValidationError(
      "context.seedMediaType is invalid"
    );
  }
  if ((seedMediaId === null) !== (seedMediaType === null)) {
    throw new RecommendationImpressionValidationError(
      "seedMediaId and seedMediaType must be supplied together"
    );
  }

  return {
    page: context.page,
    mediaType: context.mediaType,
    seedMediaId,
    seedMediaType,
  };
};

const normalizeModelVersions = (versions = {}) => {
  if (!versions || typeof versions !== "object" || Array.isArray(versions)) {
    throw new RecommendationImpressionValidationError(
      "modelVersions is invalid"
    );
  }
  const unknownFields = Object.keys(versions).filter(
    (field) => !modelVersionFields.includes(field)
  );
  if (unknownFields.length > 0) {
    throw new RecommendationImpressionValidationError(
      "modelVersions contains unknown fields"
    );
  }

  const normalized = {};
  for (const field of modelVersionFields) {
    normalized[field] = normalizeOptionalString(
      versions[field],
      `modelVersions.${field}`,
      100
    );
  }
  return normalized;
};

const normalizeItems = (items) => {
  if (!Array.isArray(items) || items.length === 0 || items.length > 500) {
    throw new RecommendationImpressionValidationError("items are invalid");
  }

  const seen = new Set();
  return items.map((item, index) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new RecommendationImpressionValidationError(
        `items[${index}] is invalid`
      );
    }
    const mediaId = item.mediaId?.toString().trim();
    if (!mediaId || mediaId.length > 64 || !mediaTypes.includes(item.mediaType)) {
      throw new RecommendationImpressionValidationError(
        `items[${index}] has an invalid media identity`
      );
    }

    const key = `${item.mediaType}:${mediaId}`;
    if (seen.has(key)) {
      throw new RecommendationImpressionValidationError(
        "items contain duplicate media"
      );
    }
    seen.add(key);

    const rank = Number(item.rank ?? index + 1);
    if (!Number.isInteger(rank) || rank < 1 || rank > 10000) {
      throw new RecommendationImpressionValidationError(
        `items[${index}].rank is invalid`
      );
    }

    let finalScore = null;
    if (item.finalScore !== undefined && item.finalScore !== null) {
      finalScore = Number(item.finalScore);
      if (!Number.isFinite(finalScore)) {
        throw new RecommendationImpressionValidationError(
          `items[${index}].finalScore is invalid`
        );
      }
    }

    if (item.sourceModels !== undefined && !Array.isArray(item.sourceModels)) {
      throw new RecommendationImpressionValidationError(
        `items[${index}].sourceModels is invalid`
      );
    }
    const sourceModels = [...new Set(item.sourceModels || [])];
    if (
      sourceModels.length > 10 ||
      sourceModels.some(
        (source) =>
          typeof source !== "string" || !source.trim() || source.length > 64
      )
    ) {
      throw new RecommendationImpressionValidationError(
        `items[${index}].sourceModels is invalid`
      );
    }

    return {
      mediaId,
      mediaType: item.mediaType,
      rank,
      finalScore,
      sourceModels: sourceModels.map((source) => source.trim()),
    };
  });
};

export const normalizeRecommendationImpression = (input) => {
  const userId = input?.userId?.toString();
  if (!userId || !mongoose.isValidObjectId(userId)) {
    throw new RecommendationImpressionValidationError("userId is invalid");
  }

  const strategy = normalizeOptionalString(input.strategy, "strategy", 64);
  if (!strategy) {
    throw new RecommendationImpressionValidationError("strategy is required");
  }

  return {
    user: userId,
    context: normalizeContext(input.context),
    strategy,
    modelVersions: normalizeModelVersions(input.modelVersions),
    items: normalizeItems(input.items),
  };
};

export const recordRecommendationImpression = async (input, options = {}) => {
  const model = options.model || recommendationImpressionModel;
  const idFactory = options.idFactory || randomUUID;
  const normalized = normalizeRecommendationImpression(input);
  const recommendationId = idFactory();
  if (
    typeof recommendationId !== "string" ||
    !recommendationId ||
    recommendationId.length > 128
  ) {
    throw new RecommendationImpressionValidationError(
      "generated recommendationId is invalid"
    );
  }

  const impression = await model.create({
    recommendationId,
    ...normalized,
  });

  return {
    recommendationId,
    strategy: normalized.strategy,
    modelVersions: normalized.modelVersions,
    impression,
  };
};

export default { recordRecommendationImpression };
