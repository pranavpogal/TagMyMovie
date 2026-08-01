import mongoose, { Schema } from "mongoose";
import modelOptions from "./model.options.js";

const genreSchema = new Schema(
  {
    id: { type: Number, required: true },
    name: { type: String, required: true, trim: true, maxlength: 100 },
  },
  { _id: false }
);

const stringArrayField = {
  type: [String],
  default: [],
};

const mediaCatalogSchema = mongoose.Schema(
  {
    tmdbId: {
      type: String,
      required: true,
      trim: true,
      maxlength: 64,
    },
    mediaType: {
      type: String,
      enum: ["movie", "tv"],
      required: true,
    },
    title: {
      type: String,
      required: true,
      trim: true,
      maxlength: 500,
    },
    originalTitle: {
      type: String,
      required: true,
      trim: true,
      maxlength: 500,
    },
    overview: {
      type: String,
      default: "",
      trim: true,
      maxlength: 10000,
    },
    genres: {
      type: [genreSchema],
      default: [],
    },
    genreIds: {
      type: [Number],
      default: [],
    },
    originalLanguage: {
      type: String,
      default: "",
      trim: true,
      lowercase: true,
      maxlength: 20,
    },
    spokenLanguages: stringArrayField,
    releaseDate: {
      type: Date,
      default: null,
    },
    releaseYear: {
      type: Number,
      default: null,
      min: 1870,
      max: 2200,
    },
    cast: stringArrayField,
    directors: stringArrayField,
    creators: stringArrayField,
    keywords: stringArrayField,
    popularity: {
      type: Number,
      default: 0,
      min: 0,
    },
    voteAverage: {
      type: Number,
      default: 0,
      min: 0,
      max: 10,
    },
    voteCount: {
      type: Number,
      default: 0,
      min: 0,
    },
    posterPath: {
      type: String,
      default: "",
      maxlength: 500,
    },
    backdropPath: {
      type: String,
      default: "",
      maxlength: 500,
    },
    featureText: {
      type: String,
      default: "",
    },
    featureHash: {
      type: String,
      default: "",
      maxlength: 128,
    },
    embedding: {
      type: [Number],
      default: [],
    },
    embeddingDimension: {
      type: Number,
      default: 0,
      min: 0,
    },
    embeddingModel: {
      type: String,
      default: null,
      maxlength: 200,
    },
    embeddingVersion: {
      type: String,
      default: null,
      maxlength: 100,
    },
    lastSyncedAt: {
      type: Date,
      required: true,
    },
  },
  { ...modelOptions, collection: "media_catalog" }
);

mediaCatalogSchema.pre("validate", function validateCatalogueConsistency(next) {
  const normalizedGenreIds = [...new Set(this.genreIds || [])];
  if (
    normalizedGenreIds.length !== (this.genreIds || []).length ||
    normalizedGenreIds.some((id) => !Number.isInteger(id) || id <= 0)
  ) {
    this.invalidate("genreIds", "genreIds must contain unique positive integers");
  }

  const genreObjectIds = (this.genres || []).map((genre) => genre.id);
  if (new Set(genreObjectIds).size !== genreObjectIds.length) {
    this.invalidate("genres", "genres must not contain duplicate IDs");
  }

  const embedding = this.embedding || [];
  if (embedding.some((value) => !Number.isFinite(value))) {
    this.invalidate("embedding", "embedding values must be finite numbers");
  }
  if (embedding.length === 0 && this.embeddingDimension !== 0) {
    this.invalidate(
      "embeddingDimension",
      "embeddingDimension must be zero when no embedding is stored"
    );
  }
  if (embedding.length > 0) {
    if (this.embeddingDimension !== embedding.length) {
      this.invalidate(
        "embeddingDimension",
        "embeddingDimension must match the embedding length"
      );
    }
    if (!this.embeddingModel || !this.embeddingVersion) {
      this.invalidate(
        "embeddingModel",
        "embeddingModel and embeddingVersion are required with an embedding"
      );
    }
  }

  next();
});

mediaCatalogSchema.index({ tmdbId: 1, mediaType: 1 }, { unique: true });
mediaCatalogSchema.index({ mediaType: 1 });
mediaCatalogSchema.index({ genreIds: 1 });
mediaCatalogSchema.index({ originalLanguage: 1 });
mediaCatalogSchema.index({ releaseYear: 1 });
mediaCatalogSchema.index({ voteCount: 1 });

export default mongoose.model("MediaCatalog", mediaCatalogSchema);
