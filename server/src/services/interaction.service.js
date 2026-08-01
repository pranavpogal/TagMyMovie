import mongoose from "mongoose";
import interactionModel, {
  interactionEventTypes,
  interactionSources,
} from "../models/interaction.model.js";

export const frontendEventTypes = [
  "search_click",
  "recommendation_click",
  "trailer_play",
  "detail_view",
];

export const frontendEventSources = {
  search_click: "search",
  recommendation_click: "recommendation",
  trailer_play: "media_detail",
  detail_view: "media_detail",
};

const minutesToMs = (environmentName, fallbackMinutes) => {
  const configuredMinutes = Number(process.env[environmentName]);
  const minutes =
    Number.isFinite(configuredMinutes) && configuredMinutes > 0
      ? configuredMinutes
      : fallbackMinutes;
  return minutes * 60 * 1000;
};

export const interactionDeduplicationWindowsMs = {
  detail_view: minutesToMs("INTERACTION_DETAIL_VIEW_DEDUP_MINUTES", 15),
  search_click: minutesToMs("INTERACTION_SEARCH_CLICK_DEDUP_MINUTES", 5),
  trailer_play: minutesToMs("INTERACTION_TRAILER_PLAY_DEDUP_MINUTES", 15),
  recommendation_click: minutesToMs(
    "INTERACTION_RECOMMENDATION_CLICK_DEDUP_MINUTES",
    5
  ),
};

const metadataMaxBytes = 2048;
const metadataMaxKeys = 20;
const metadataMaxArrayItems = 20;
const metadataKeyPattern = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/;

export class InteractionValidationError extends Error {
  constructor(message) {
    super(message);
    this.name = "InteractionValidationError";
  }
}

const optionalString = (value, field, maxLength) => {
  if (value === undefined || value === null || value === "") return null;
  if (typeof value !== "string") {
    throw new InteractionValidationError(`${field} must be a string`);
  }

  const normalized = value.trim();
  if (!normalized || normalized.length > maxLength) {
    throw new InteractionValidationError(`${field} is invalid`);
  }
  return normalized;
};

const sanitizeMetadataValue = (value) => {
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "boolean" ||
    (typeof value === "number" && Number.isFinite(value))
  ) {
    return value;
  }

  if (Array.isArray(value) && value.length <= metadataMaxArrayItems) {
    const sanitized = value.map(sanitizeMetadataValue);
    if (sanitized.every((item) => item !== undefined && !Array.isArray(item))) {
      return sanitized;
    }
  }

  return undefined;
};

export const sanitizeInteractionMetadata = (metadata = {}) => {
  if (metadata === null || metadata === undefined) return {};
  if (
    typeof metadata !== "object" ||
    Array.isArray(metadata) ||
    Object.getPrototypeOf(metadata) !== Object.prototype
  ) {
    throw new InteractionValidationError("metadata must be a plain object");
  }

  const entries = Object.entries(metadata);
  if (entries.length > metadataMaxKeys) {
    throw new InteractionValidationError("metadata has too many fields");
  }

  const sanitized = {};
  for (const [key, value] of entries) {
    if (!metadataKeyPattern.test(key) || key.startsWith("$")) {
      throw new InteractionValidationError("metadata contains an invalid key");
    }

    const sanitizedValue = sanitizeMetadataValue(value);
    if (sanitizedValue === undefined) {
      throw new InteractionValidationError(`metadata.${key} is invalid`);
    }
    sanitized[key] = sanitizedValue;
  }

  if (Buffer.byteLength(JSON.stringify(sanitized), "utf8") > metadataMaxBytes) {
    throw new InteractionValidationError("metadata is too large");
  }

  return sanitized;
};

export const normalizeInteraction = (input) => {
  if (!input || typeof input !== "object") {
    throw new InteractionValidationError("interaction is required");
  }

  const userId = input.userId?.toString();
  if (!userId || !mongoose.isValidObjectId(userId)) {
    throw new InteractionValidationError("userId is invalid");
  }

  const mediaId = input.mediaId?.toString().trim();
  if (!mediaId || mediaId.length > 64) {
    throw new InteractionValidationError("mediaId is invalid");
  }
  if (!['movie', 'tv'].includes(input.mediaType)) {
    throw new InteractionValidationError("mediaType is invalid");
  }
  if (!interactionEventTypes.includes(input.eventType)) {
    throw new InteractionValidationError("eventType is invalid");
  }

  const value = input.value === undefined ? 1 : Number(input.value);
  if (!Number.isFinite(value) || value < -100 || value > 100) {
    throw new InteractionValidationError("value is invalid");
  }

  const source = input.source || "unknown";
  if (!interactionSources.includes(source)) {
    throw new InteractionValidationError("source is invalid");
  }

  let recommendationRank = null;
  if (input.recommendationRank !== undefined && input.recommendationRank !== null) {
    recommendationRank = Number(input.recommendationRank);
    if (
      !Number.isInteger(recommendationRank) ||
      recommendationRank < 0 ||
      recommendationRank > 10000
    ) {
      throw new InteractionValidationError("recommendationRank is invalid");
    }
  }

  return {
    user: userId,
    mediaId,
    mediaType: input.mediaType,
    eventType: input.eventType,
    value,
    source,
    recommendationId: optionalString(
      input.recommendationId,
      "recommendationId",
      128
    ),
    recommendationStrategy: optionalString(
      input.recommendationStrategy,
      "recommendationStrategy",
      64
    ),
    recommendationRank,
    sessionId: optionalString(input.sessionId, "sessionId", 128),
    metadata: sanitizeInteractionMetadata(input.metadata),
  };
};

export const buildDeduplicationFilter = (interaction, now = new Date()) => {
  if (
    interaction.eventType === "recommendation_impression" &&
    interaction.recommendationId
  ) {
    return {
      user: interaction.user,
      eventType: interaction.eventType,
      recommendationId: interaction.recommendationId,
    };
  }

  if (
    interaction.eventType === "recommendation_click" &&
    interaction.recommendationId
  ) {
    return {
      user: interaction.user,
      eventType: interaction.eventType,
      recommendationId: interaction.recommendationId,
      mediaType: interaction.mediaType,
      mediaId: interaction.mediaId,
    };
  }

  const windowMs = interactionDeduplicationWindowsMs[interaction.eventType];
  if (!windowMs) return null;

  const filter = {
    user: interaction.user,
    mediaType: interaction.mediaType,
    mediaId: interaction.mediaId,
    eventType: interaction.eventType,
    createdAt: { $gte: new Date(now.getTime() - windowMs) },
  };

  if (interaction.sessionId) filter.sessionId = interaction.sessionId;
  return filter;
};

export const recordInteraction = async (input, options = {}) => {
  const model = options.model || interactionModel;
  const now = options.now || new Date();
  const interaction = normalizeInteraction(input);
  const deduplicationFilter = buildDeduplicationFilter(interaction, now);

  if (deduplicationFilter) {
    const existing = await model.findOne(deduplicationFilter);
    if (existing) {
      return { recorded: false, deduplicated: true, interaction: existing };
    }
  }

  const created = await model.create(interaction);
  return { recorded: true, deduplicated: false, interaction: created };
};

export const recordInteractionBestEffort = (input) => {
  setImmediate(() => {
    recordInteraction(input).catch((error) => {
      console.warn("Interaction analytics write failed", {
        eventType: input?.eventType,
        errorName: error?.name,
      });
    });
  });
};

export default {
  recordInteraction,
  recordInteractionBestEffort,
};
