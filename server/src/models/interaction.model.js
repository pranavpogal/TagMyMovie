import mongoose, { Schema } from "mongoose";
import modelOptions from "./model.options.js";

export const interactionEventTypes = [
  "detail_view",
  "search_click",
  "recommendation_impression",
  "recommendation_click",
  "trailer_play",
  "favourite_add",
  "favourite_remove",
  "review_create",
  "review_update",
  "rating_submit",
  "not_interested",
  "onboarding_favourite",
];

export const interactionSources = [
  "home",
  "search",
  "media_detail",
  "recommendation",
  "onboarding",
  "profile",
  "unknown",
];

const interactionSchema = mongoose.Schema(
  {
    user: {
      type: Schema.Types.ObjectId,
      ref: "User",
      required: true,
    },
    mediaId: {
      type: String,
      required: true,
      trim: true,
    },
    mediaType: {
      type: String,
      enum: ["movie", "tv"],
      required: true,
    },
    eventType: {
      type: String,
      enum: interactionEventTypes,
      required: true,
    },
    value: {
      type: Number,
      required: true,
      default: 1,
    },
    source: {
      type: String,
      enum: interactionSources,
      required: true,
      default: "unknown",
    },
    recommendationId: {
      type: String,
      default: null,
      maxlength: 128,
    },
    recommendationStrategy: {
      type: String,
      default: null,
      maxlength: 64,
    },
    recommendationRank: {
      type: Number,
      default: null,
      min: 0,
    },
    sessionId: {
      type: String,
      default: null,
      maxlength: 128,
    },
    metadata: {
      type: Schema.Types.Mixed,
      default: {},
    },
  },
  modelOptions
);

interactionSchema.index({ user: 1, createdAt: -1 });
interactionSchema.index({ user: 1, mediaType: 1, mediaId: 1 });
interactionSchema.index({ user: 1, eventType: 1, createdAt: -1 });
interactionSchema.index(
  { recommendationId: 1 },
  { partialFilterExpression: { recommendationId: { $type: "string" } } }
);
interactionSchema.index({ mediaType: 1, mediaId: 1, eventType: 1 });

export default mongoose.model("Interaction", interactionSchema);
