import responseHandler from "../handlers/response.handler.js";
import userPreferenceModel from "../models/userPreference.model.js";
import {
  normalizePreferencePayload,
  PreferenceValidationError,
} from "../validators/preference.validator.js";

const get = async (req, res) => {
  try {
    const preferences = await userPreferenceModel.findOneAndUpdate(
      { user: req.user.id },
      { $setOnInsert: { user: req.user.id } },
      { new: true, upsert: true, setDefaultsOnInsert: true }
    );
    responseHandler.ok(res, preferences);
  } catch {
    responseHandler.error(res);
  }
};

const update = async (req, res) => {
  try {
    const updates = normalizePreferencePayload(req.body);
    const preferences = await userPreferenceModel.findOneAndUpdate(
      { user: req.user.id },
      { $set: updates, $setOnInsert: { user: req.user.id } },
      { new: true, upsert: true, runValidators: true, setDefaultsOnInsert: true }
    );
    responseHandler.ok(res, preferences);
  } catch (error) {
    if (error instanceof PreferenceValidationError) {
      return responseHandler.badrequest(res, error.message);
    }
    responseHandler.error(res);
  }
};

const reset = async (req, res) => {
  try {
    if (req.body.confirm !== true) {
      return responseHandler.badrequest(res, "reset confirmation is required");
    }

    await userPreferenceModel.deleteOne({ user: req.user.id });
    responseHandler.ok(res, {
      reset: true,
      interactionHistoryCleared: false,
    });
  } catch {
    responseHandler.error(res);
  }
};

export default { get, update, reset };
