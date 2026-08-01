import privateClient from "../client/private.client";

const reviewEndpoints = {
  list: "reviews",
  add: "reviews",
  update: ({ reviewId }) => `reviews/${reviewId}`,
  remove: ({ reviewId }) => `reviews/${reviewId}`,
};

const reviewApi = {
  add: async ({ mediaId, mediaType, mediaTitle, mediaPoster, content, rating }) => {
    try {
      const response = await privateClient.post(reviewEndpoints.add, {
        mediaId,
        mediaType,
        mediaTitle,
        mediaPoster,
        content,
        rating,
      });

      return { response };
    } catch (err) {
      return { err };
    }
  },
  update: async ({ reviewId, content, rating }) => {
    try {
      const response = await privateClient.put(
        reviewEndpoints.update({ reviewId }),
        { content, rating }
      );
      return { response };
    } catch (err) {
      return { err };
    }
  },
  remove: async ({ reviewId }) => {
    try {
      const response = await privateClient.delete(
        reviewEndpoints.remove({ reviewId })
      );

      return { response };
    } catch (err) {
      return { err };
    }
  },
  getList: async () => {
    try {
      const response = await privateClient.get(reviewEndpoints.list);

      return { response };
    } catch (err) {
      return { err };
    }
  },
};

export default reviewApi;
