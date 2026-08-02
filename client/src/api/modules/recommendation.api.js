import privateClient from "../client/private.client";

const recommendationApi = {
  get: async (params = {}) => {
    try {
      const response = await privateClient.get("recommendations", { params });
      return { response };
    } catch (err) {
      return { err };
    }
  },
};

export default recommendationApi;
