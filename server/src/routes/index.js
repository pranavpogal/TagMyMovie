import express from "express";
import userRoute from "./user.route.js";
import mediaRoute from "./media.route.js";
import personRoute from "./person.route.js";
import reviewRoute from "./review.route.js";
import interactionRoute from "./interaction.route.js";
import recommendationRoute from "./recommendation.route.js";

const router = express.Router();

router.use("/user", userRoute);
router.use("/person", personRoute);
router.use("/reviews", reviewRoute);
router.use("/interactions", interactionRoute);
router.use("/recommendations", recommendationRoute);
router.use("/:mediaType", mediaRoute);

export default router;
