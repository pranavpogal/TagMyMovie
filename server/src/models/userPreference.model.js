import mongoose, { Schema } from "mongoose";
import modelOptions from "./model.options.js";

const seedMediaSchema = new Schema(
  {
    mediaId: { type: String, required: true, trim: true },
    mediaType: {
      type: String,
      enum: ["movie", "tv"],
      required: true,
    },
    title: { type: String, required: true, trim: true, maxlength: 300 },
    posterPath: { type: String, default: "", maxlength: 500 },
  },
  { _id: false }
);

const userPreferenceSchema = mongoose.Schema(
  {
    user: {
      type: Schema.Types.ObjectId,
      ref: "User",
      required: true,
      unique: true,
    },
    preferredGenreIds: {
      type: [Number],
      default: [],
    },
    preferredLanguages: {
      type: [String],
      default: [],
    },
    favouriteSeedMedia: {
      type: [seedMediaSchema],
      default: [],
    },
    preferredReleasePeriods: {
      type: [String],
      default: [],
    },
    excludePreviouslyFavourited: {
      type: Boolean,
      default: true,
    },
    excludePreviouslyRated: {
      type: Boolean,
      default: true,
    },
    onboardingCompleted: {
      type: Boolean,
      default: false,
    },
    onboardingSkipped: {
      type: Boolean,
      default: false,
    },
  },
  modelOptions
);

export default mongoose.model("UserPreference", userPreferenceSchema);
