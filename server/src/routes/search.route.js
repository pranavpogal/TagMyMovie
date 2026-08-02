import express from "express";
import semanticSearchController from "../controllers/semanticSearch.controller.js";

const router = express.Router();
router.get("/semantic", semanticSearchController.search);

export default router;
