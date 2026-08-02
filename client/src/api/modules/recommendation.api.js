import privateClient from "../client/private.client";

const recommendationApi = {
  get: async (params = {}) => {
    try {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
          searchParams.set(key, String(value));
        }
      });
      const query = searchParams.toString();
      const response = await privateClient.get(
        query ? `recommendations?${query}` : "recommendations"
      );
      return { response };
    } catch (err) {
      return { err };
    }
  },
};

export default recommendationApi;
