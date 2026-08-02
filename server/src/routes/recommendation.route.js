import express from "express";
import recommendationController from "../controllers/recommendation.controller.js";
import tokenMiddleware from "../middlewares/token.middleware.js";

const router = express.Router();
router.get("/", tokenMiddleware.auth, recommendationController.get);
export default router;
