import responseHandler from "../handlers/response.handler.js";
import reviewModel from "../models/review.model.js";
import { recordInteractionBestEffort } from "../services/interaction.service.js";

const create = async (req, res) => {
  try {
    const review = new reviewModel({
      user: req.user.id,
      mediaId: req.body.mediaId,
      mediaType: req.body.mediaType,
      mediaTitle: req.body.mediaTitle,
      mediaPoster: req.body.mediaPoster,
      content: req.body.content,
    });

    await review.save();

    recordInteractionBestEffort({
      userId: req.user.id,
      mediaId: review.mediaId,
      mediaType: review.mediaType,
      eventType: "review_create",
      value: 1,
      source: "media_detail",
    });

    responseHandler.created(res, {
      ...review._doc,
      id: review.id,
      user: req.user,
    });
  } catch {
    responseHandler.error(res);
  }
};

const remove = async (req, res) => {
  try {
    const { reviewId } = req.params;

    const review = await reviewModel.findOne({
      _id: reviewId,
      user: req.user.id,
    });

    if (!review) return responseHandler.notfound(res);

    await review.deleteOne();

    responseHandler.ok(res);
  } catch {
    responseHandler.error(res);
  }
};

const getReviewsOfUser = async (req, res) => {
  try {
    const reviews = await reviewModel
      .find({
        user: req.user.id,
      })
      .sort("-createdAt");

    responseHandler.ok(res, reviews);
  } catch {
    responseHandler.error(res);
  }
};

export default { create, remove, getReviewsOfUser };
