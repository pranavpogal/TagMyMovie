import express from "express";
import interactionController from "../controllers/interaction.controller.js";
import tokenMiddleware from "../middlewares/token.middleware.js";

const router = express.Router();

router.post("/", tokenMiddleware.auth, interactionController.create);

export default router;
