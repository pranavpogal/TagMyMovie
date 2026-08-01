import responseHandler from "../handlers/response.handler.js";
import favouriteModel from "../models/favourite.model.js";
import { recordInteractionBestEffort } from "../services/interaction.service.js";

const addFavourite = async (req, res) => {
  try {
    const isFavourite = await favouriteModel.findOne({
      user: req.user.id,
      mediaId: req.body.mediaId,
      mediaType: req.body.mediaType,
    });

    if (isFavourite) return responseHandler.ok(res, isFavourite);

    const favourite = new favouriteModel({
      user: req.user.id,
      mediaId: req.body.mediaId,
      mediaType: req.body.mediaType,
      mediaTitle: req.body.mediaTitle,
      mediaPoster: req.body.mediaPoster,
      mediaRate: req.body.mediaRate,
    });

    await favourite.save();

    recordInteractionBestEffort({
      userId: req.user.id,
      mediaId: favourite.mediaId,
      mediaType: favourite.mediaType,
      eventType: "favourite_add",
      value: 1,
      source: "media_detail",
      recommendationId: req.body.recommendationId,
      recommendationStrategy: req.body.recommendationStrategy,
      sessionId: req.body.sessionId,
    });

    responseHandler.created(res, favourite);
  } catch {
    responseHandler.error(res);
  }
};

const removeFavourite = async (req, res) => {
  try {
    const { favouriteId } = req.params;

    const favourite = await favouriteModel.findOne({
      user: req.user.id,
      _id: favouriteId,
    });

    if (!favourite) return responseHandler.notfound(res);

    await favourite.deleteOne();

    recordInteractionBestEffort({
      userId: req.user.id,
      mediaId: favourite.mediaId,
      mediaType: favourite.mediaType,
      eventType: "favourite_remove",
      value: -1,
      source: "unknown",
    });

    responseHandler.ok(res);
  } catch {
    responseHandler.error(res);
  }
};

const getFavouritesOfUser = async (req, res) => {
  try {
    const favourite = await favouriteModel
      .find({ user: req.user.id })
      .sort("-createdAt");

    responseHandler.ok(res, favourite);
  } catch {
    responseHandler.error(res);
  }
};

export default { addFavourite, removeFavourite, getFavouritesOfUser };
