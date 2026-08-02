import privateClient from "../client/private.client";
import publicClient from "../client/public.client";

const mediaEndpoints = {
  list: ({ mediaType, mediaCategory, page }) =>
    `${mediaType}/${mediaCategory}?page=${page}`,
  detail: ({ mediaType, mediaId }) => `${mediaType}/detail/${mediaId}`,
  search: ({ mediaType, query, page }) =>
    `${mediaType}/search?query=${query}&page=${page}`,
};

const mediaApi = {
  getList: async ({ mediaType, mediaCategory, page }) => {
    try {
      const response = await publicClient.get(
        mediaEndpoints.list({ mediaType, mediaCategory, page })
      );

      return { response };
    } catch (err) {
      return { err };
    }
  },
  getDetail: async ({ mediaType, mediaId }) => {
    try {
      const response = await privateClient.get(
        mediaEndpoints.detail({ mediaType, mediaId })
      );

      return { response };
    } catch (err) {
      return { err };
    }
  },
  search: async ({ mediaType, query, page }) => {
    try {
      const response = await publicClient.get(
        mediaEndpoints.search({ mediaType, query, page })
      );

      return { response };
    } catch (err) {
      return { err };
    }
  },
  semanticSearch: async ({ mediaType, query, language, genreIds, limit = 20 }) => {
    try {
      const params = new URLSearchParams({ mediaType, query, limit: String(limit) });
      if (language) params.set("language", language);
      if (genreIds?.length) params.set("genreIds", genreIds.join(","));
      const response = await publicClient.get(`search/semantic?${params.toString()}`);
      return { response };
    } catch (err) {
      return { err };
    }
  },
};

export default mediaApi;
