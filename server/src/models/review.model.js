import mongoose, { Schema } from "mongoose";
import modelOptions from "./model.options.js";

const reviewSchema = mongoose.Schema(
  {
    user: {
      type: Schema.Types.ObjectId,
      ref: "User",
      required: true,
    },
    content: {
      type: String,
      trim: true,
      default: "",
      maxlength: 2000,
    },
    rating: {
      type: Number,
      min: 1,
      max: 10,
      validate: {
        validator: (value) =>
          value === null ||
          value === undefined ||
          Number.isInteger(value * 2),
        message: "rating must use half-point steps",
      },
    },
    mediaType: {
      type: String,
      enum: ["tv", "movie"],
      required: true,
    },
    mediaId: {
      type: String,
      required: true,
    },
    mediaTitle: {
      type: String,
      required: true,
    },
    mediaPoster: {
      type: String,
      required: true,
    },
  },
  modelOptions
);

reviewSchema.index({ user: 1, mediaType: 1, mediaId: 1 });
reviewSchema.index({ mediaType: 1, mediaId: 1, createdAt: -1 });

export default mongoose.model("Review", reviewSchema);
