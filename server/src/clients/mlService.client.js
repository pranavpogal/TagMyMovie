import axios from "axios";

export class MlServiceClientError extends Error {
  constructor(message) {
    super(message);
    this.name = "MlServiceClientError";
  }
}

export const createMlServiceClient = (options = {}) => {
  const baseURL = (options.baseURL || process.env.ML_SERVICE_URL || "http://localhost:8000").trim();
  const timeout = Number(options.timeout || process.env.ML_REQUEST_TIMEOUT_MS || 5000);
  const internalKey = (options.internalKey || process.env.ML_INTERNAL_KEY || "").trim();
  if (!/^https?:\/\//.test(baseURL) || !Number.isInteger(timeout) || timeout < 100 || timeout > 30000) {
    throw new MlServiceClientError("ML service configuration is invalid");
  }
  const client = options.axiosInstance || axios.create({ baseURL, timeout });
  return {
    async recommendations(userId, parameters) {
      try {
        const response = await client.get(`/recommendations/${encodeURIComponent(userId)}`, {
          params: {
            media_type: parameters.mediaType,
            limit: parameters.limit,
            context: parameters.context,
            seed_media_id: parameters.seedMediaId || undefined,
            seed_media_type: parameters.seedMediaType || undefined,
            exclude_seen: parameters.excludeSeen,
          },
          headers: {
            Accept: "application/json",
            ...(internalKey ? { "X-Internal-Key": internalKey } : {}),
          },
        });
        return response.data;
      } catch (error) {
        throw new MlServiceClientError(
          error?.code === "ECONNABORTED" ? "ML service timed out" : "ML service request failed"
        );
      }
    },
  };
};

export default createMlServiceClient();
