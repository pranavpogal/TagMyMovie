import responseHandler from "../handlers/response.handler.js";
import semanticSearchService, { SemanticSearchRequestError } from "../services/semanticSearch.service.js";

const search = async (req, res) => {
  try {
    return responseHandler.ok(res, await semanticSearchService.semanticSearch(req.query));
  } catch (error) {
    if (error instanceof SemanticSearchRequestError) {
      return responseHandler.badrequest(res, error.message);
    }
    console.warn("Semantic search failed", { errorName: error?.name });
    return responseHandler.error(res);
  }
};

export default { search };
