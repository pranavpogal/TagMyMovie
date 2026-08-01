export class PreferenceValidationError extends Error {
  constructor(message) {
    super(message);
    this.name = "PreferenceValidationError";
  }
}

const unique = (values) => [...new Set(values)];

const validateArray = (value, field, maxLength) => {
  if (!Array.isArray(value) || value.length > maxLength) {
    throw new PreferenceValidationError(`${field} is invalid`);
  }
};

const normalizeGenreIds = (value) => {
  validateArray(value, "preferredGenreIds", 30);
  const genreIds = value.map(Number);
  if (genreIds.some((id) => !Number.isInteger(id) || id <= 0)) {
    throw new PreferenceValidationError("preferredGenreIds is invalid");
  }
  return unique(genreIds);
};

const normalizeLanguages = (value) => {
  validateArray(value, "preferredLanguages", 20);
  const languages = value.map((language) => language?.toString().trim().toLowerCase());
  if (languages.some((language) => !/^[a-z]{2,3}$/.test(language))) {
    throw new PreferenceValidationError("preferredLanguages is invalid");
  }
  return unique(languages);
};

const normalizeSeedMedia = (value) => {
  validateArray(value, "favouriteSeedMedia", 20);
  const seen = new Set();

  return value.map((media) => {
    if (!media || typeof media !== "object" || Array.isArray(media)) {
      throw new PreferenceValidationError("favouriteSeedMedia is invalid");
    }

    const mediaId = media.mediaId?.toString().trim();
    const title = media.title?.toString().trim();
    const posterPath = media.posterPath?.toString().trim() || "";
    if (
      !mediaId ||
      mediaId.length > 64 ||
      !["movie", "tv"].includes(media.mediaType) ||
      !title ||
      title.length > 300 ||
      posterPath.length > 500
    ) {
      throw new PreferenceValidationError("favouriteSeedMedia is invalid");
    }

    const key = `${media.mediaType}:${mediaId}`;
    if (seen.has(key)) {
      throw new PreferenceValidationError("favouriteSeedMedia contains duplicates");
    }
    seen.add(key);

    return { mediaId, mediaType: media.mediaType, title, posterPath };
  });
};

const normalizeReleasePeriods = (value) => {
  validateArray(value, "preferredReleasePeriods", 10);
  const periods = value.map((period) => period?.toString().trim());
  if (
    periods.some(
      (period) => !period || period.length > 32 || !/^[A-Za-z0-9_-]+$/.test(period)
    )
  ) {
    throw new PreferenceValidationError("preferredReleasePeriods is invalid");
  }
  return unique(periods);
};

const preferenceNormalizers = {
  preferredGenreIds: normalizeGenreIds,
  preferredLanguages: normalizeLanguages,
  favouriteSeedMedia: normalizeSeedMedia,
  preferredReleasePeriods: normalizeReleasePeriods,
  excludePreviouslyFavourited: (value) => {
    if (typeof value !== "boolean") {
      throw new PreferenceValidationError("excludePreviouslyFavourited is invalid");
    }
    return value;
  },
  excludePreviouslyRated: (value) => {
    if (typeof value !== "boolean") {
      throw new PreferenceValidationError("excludePreviouslyRated is invalid");
    }
    return value;
  },
  onboardingCompleted: (value) => {
    if (typeof value !== "boolean") {
      throw new PreferenceValidationError("onboardingCompleted is invalid");
    }
    return value;
  },
  onboardingSkipped: (value) => {
    if (typeof value !== "boolean") {
      throw new PreferenceValidationError("onboardingSkipped is invalid");
    }
    return value;
  },
};

export const normalizePreferencePayload = (payload) => {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new PreferenceValidationError("preferences are required");
  }

  const normalized = {};
  for (const [field, value] of Object.entries(payload)) {
    const normalize = preferenceNormalizers[field];
    if (!normalize) {
      throw new PreferenceValidationError(`${field} is not allowed`);
    }
    normalized[field] = normalize(value);
  }

  if (Object.keys(normalized).length === 0) {
    throw new PreferenceValidationError("at least one preference is required");
  }
  if (normalized.onboardingCompleted === true) {
    normalized.onboardingSkipped = false;
  } else if (normalized.onboardingSkipped === true) {
    normalized.onboardingCompleted = false;
  }
  return normalized;
};
