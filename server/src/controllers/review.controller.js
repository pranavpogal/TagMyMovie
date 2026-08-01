import responseHandler from "../handlers/response.handler.js";
import reviewModel from "../models/review.model.js";
import { recordInteractionBestEffort } from "../services/interaction.service.js";
import {
  normalizeReviewPayload,
  ReviewValidationError,
  validateFinalReview,
} from "../validators/review.validator.js";

const create = async (req, res) => {
  try {
    const normalized = normalizeReviewPayload(req.body);
    const existingReview = await reviewModel.findOne({
      user: req.user.id,
      mediaId: req.body.mediaId,
      mediaType: req.body.mediaType,
    });

    if (existingReview) {
      return responseHandler.badrequest(
        res,
        "You already reviewed this title; update the existing review instead"
      );
    }

    const review = new reviewModel({
      user: req.user.id,
      mediaId: req.body.mediaId,
      mediaType: req.body.mediaType,
      mediaTitle: req.body.mediaTitle,
      mediaPoster: req.body.mediaPoster,
      content: normalized.content,
      rating: normalized.rating,
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

    if (review.rating !== null && review.rating !== undefined) {
      recordInteractionBestEffort({
        userId: req.user.id,
        mediaId: review.mediaId,
        mediaType: review.mediaType,
        eventType: "rating_submit",
        value: review.rating,
        source: "media_detail",
      });
    }

    responseHandler.created(res, {
      ...review._doc,
      id: review.id,
      user: req.user,
    });
  } catch (error) {
    if (error instanceof ReviewValidationError) {
      return responseHandler.badrequest(res, error.message);
    }
    responseHandler.error(res);
  }
};

const update = async (req, res) => {
  try {
    const review = await reviewModel.findOne({
      _id: req.params.reviewId,
      user: req.user.id,
    });

    if (!review) return responseHandler.notfound(res);

    const normalized = normalizeReviewPayload(req.body, { partial: true });
    const nextContent =
      normalized.content === undefined ? review.content : normalized.content;
    const nextRating =
      normalized.rating === undefined ? review.rating : normalized.rating;

    validateFinalReview({ content: nextContent, rating: nextRating });

    review.content = nextContent;
    review.rating = nextRating;
    await review.save();

    recordInteractionBestEffort({
      userId: req.user.id,
      mediaId: review.mediaId,
      mediaType: review.mediaType,
      eventType: "review_update",
      value: 1,
      source: "media_detail",
    });

    if (normalized.rating !== undefined) {
      recordInteractionBestEffort({
        userId: req.user.id,
        mediaId: review.mediaId,
        mediaType: review.mediaType,
        eventType: "rating_submit",
        value: review.rating,
        source: "media_detail",
      });
    }

    responseHandler.ok(res, {
      ...review.toObject(),
      user: req.user,
    });
  } catch (error) {
    if (error instanceof ReviewValidationError) {
      return responseHandler.badrequest(res, error.message);
    }
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

export default { create, update, remove, getReviewsOfUser };
