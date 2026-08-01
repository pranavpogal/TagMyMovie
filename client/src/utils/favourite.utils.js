const favouriteUtils = {
  check: ({ listFavourites, mediaId, mediaType }) =>
    listFavourites &&
    listFavourites.find(
      (e) =>
        e.mediaType === mediaType &&
        e.mediaId.toString() === mediaId.toString()
    ) !==
      undefined,
};

export default favouriteUtils;
