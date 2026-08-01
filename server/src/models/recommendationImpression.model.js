import mongoose, { Schema } from "mongoose";
import modelOptions from "./model.options.js";

const modelVersionsSchema = new Schema(
  {
    embedding: { type: String, default: null, maxlength: 100 },
    collaborative: { type: String, default: null, maxlength: 100 },
    profile: { type: String, default: null, maxlength: 100 },
    ranking: { type: String, default: null, maxlength: 100 },
    diversity: { type: String, default: null, maxlength: 100 },
  },
  { _id: false }
);

const contextSchema = new Schema(
  {
    page: {
      type: String,
      enum: ["home", "media_detail", "other"],
      required: true,
    },
    mediaType: {
      type: String,
      enum: ["movie", "tv"],
      required: true,
    },
    seedMediaId: { type: String, default: null, maxlength: 64 },
    seedMediaType: {
      type: String,
      enum: ["movie", "tv", null],
      default: null,
    },
  },
  { _id: false }
);

const impressionItemSchema = new Schema(
  {
    mediaId: { type: String, required: true, maxlength: 64 },
    mediaType: {
      type: String,
      enum: ["movie", "tv"],
      required: true,
    },
    rank: { type: Number, required: true, min: 1 },
    finalScore: { type: Number, default: null },
    sourceModels: { type: [String], default: [] },
  },
  { _id: false }
);

const recommendationImpressionSchema = mongoose.Schema(
  {
    recommendationId: {
      type: String,
      required: true,
      unique: true,
      maxlength: 128,
    },
    user: {
      type: Schema.Types.ObjectId,
      ref: "User",
      required: true,
    },
    context: {
      type: contextSchema,
      required: true,
    },
    strategy: {
      type: String,
      required: true,
      maxlength: 64,
    },
    modelVersions: {
      type: modelVersionsSchema,
      default: () => ({}),
    },
    items: {
      type: [impressionItemSchema],
      required: true,
      validate: {
        validator: (items) => items.length > 0 && items.length <= 500,
        message: "items must contain between 1 and 500 recommendations",
      },
    },
  },
  modelOptions
);

recommendationImpressionSchema.index({ user: 1, createdAt: -1 });
recommendationImpressionSchema.index({ "context.page": 1, createdAt: -1 });

const configuredRetentionDays = Number(
  process.env.RECOMMENDATION_IMPRESSION_RETENTION_DAYS
);
const retentionDays =
  Number.isFinite(configuredRetentionDays) && configuredRetentionDays > 0
    ? configuredRetentionDays
    : 90;

recommendationImpressionSchema.index(
  { createdAt: 1 },
  { expireAfterSeconds: Math.round(retentionDays * 24 * 60 * 60) }
);

export default mongoose.model(
  "RecommendationImpression",
  recommendationImpressionSchema
);
