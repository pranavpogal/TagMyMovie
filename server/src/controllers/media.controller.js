import responseHandler from "../handlers/response.handler.js";
import tmdbApi from "../tmdb/tmdb.api.js";
import userModel from "../models/user.model.js";
import favouriteModel from "../models/favourite.model.js";
import reviewModel from "../models/review.model.js";
import tokenMiddlerware from "../middlewares/token.middleware.js";

const getList = async (req, res) => {
  try {
    const { page } = req.query;
    const { mediaType, mediaCategory } = req.params;

    const response = await tmdbApi.mediaList({
      mediaType,
      mediaCategory,
      page,
    });

    return responseHandler.ok(res, response);
  } catch (e) {
    console.log(e);
    responseHandler.error(res);
  }
};

const getGenres = async (req, res) => {
  try {
    const { mediaType } = req.params;

    const response = await tmdbApi.mediaGenres({ mediaType });

    return responseHandler.ok(res, response);
  } catch {
    responseHandler.error(res);
  }
};

const search = async (req, res) => {
  try {
    const { mediaType } = req.params;
    const { query, page } = req.query;

    const response = await tmdbApi.mediaSearch({
      query,
      page,
      mediaType: mediaType === "people" ? "person" : mediaType,
    });

    responseHandler.ok(res, response);
  } catch {
    responseHandler.error(res);
  }
};

const getDetail = async (req, res) => {
  try {
    const { mediaType, mediaId } = req.params;
    const params = { mediaType, mediaId };

    const media = await tmdbApi.mediaDetail(params);

    // Fire all sub-requests in parallel — total wait = slowest one, not sum of all
    const [credits, videos, recommend, images] = await Promise.all([
      tmdbApi.mediaCredits(params).catch(() => ({ cast: [], crew: [] })),
      tmdbApi.mediaVideos(params).catch(() => ({ results: [] })),
      tmdbApi.mediaRecommend(params).catch(() => ({ results: [] })),
      tmdbApi.mediaImages(params).catch(() => ({ backdrops: [], posters: [] })),
    ]);

    media.credits = credits;
    media.videos = videos;
    media.recommend = recommend.results;
    media.images = images;

    const tokenDecoded = tokenMiddlerware.tokenDecode(req);

    if (tokenDecoded) {
      const user = await userModel.findById(tokenDecoded.data);
      if (user) {
        const isFavourite = await favouriteModel.findOne({
          user: user.id,
          mediaId,
          mediaType,
        });
        media.isFavourite = isFavourite !== null;
      }
    }

    media.reviews = await reviewModel
      .find({ mediaId, mediaType })
      .populate("user")
      .sort("-createdAt")
      .catch(() => []);

    responseHandler.ok(res, media);
  } catch (e) {
    console.log(e);
    responseHandler.error(res);
  }
};

export default { getList, getGenres, search, getDetail };
