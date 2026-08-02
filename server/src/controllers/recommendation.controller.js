import responseHandler from "../handlers/response.handler.js";
import recommendationService, { RecommendationRequestError } from "../services/recommendation.service.js";

const get = async (req, res) => {
  try {
    const response = await recommendationService.getRecommendations({
      userId: req.user.id,
      query: req.query,
    });
    return responseHandler.ok(res, response);
  } catch (error) {
    if (error instanceof RecommendationRequestError) {
      return responseHandler.badrequest(res, error.message);
    }
    console.error("Recommendation request failed", { errorName: error?.name });
    return responseHandler.error(res);
  }
};

export default { get };
