import responseHandler from "../handlers/response.handler.js";
import {
  frontendEventTypes,
  frontendEventSources,
  InteractionValidationError,
  recordInteraction,
} from "../services/interaction.service.js";

const create = async (req, res) => {
  try {
    if (!frontendEventTypes.includes(req.body.eventType)) {
      return responseHandler.badrequest(res, "eventType is not allowed");
    }

    const result = await recordInteraction({
      userId: req.user.id,
      mediaId: req.body.mediaId,
      mediaType: req.body.mediaType,
      eventType: req.body.eventType,
      value: 1,
      source: frontendEventSources[req.body.eventType],
      recommendationId: req.body.recommendationId,
      recommendationStrategy: req.body.recommendationStrategy,
      recommendationRank: req.body.recommendationRank,
      sessionId: req.body.sessionId,
      metadata: req.body.metadata,
    });

    return responseHandler.created(res, {
      recorded: result.recorded,
      deduplicated: result.deduplicated,
    });
  } catch (error) {
    if (error instanceof InteractionValidationError) {
      return responseHandler.badrequest(res, error.message);
    }
    return responseHandler.error(res);
  }
};

export default { create };
