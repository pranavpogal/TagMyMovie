import "dotenv/config";
import fs from "node:fs/promises";
import path from "node:path";
import mongoose from "mongoose";
import reviewModel from "../src/models/review.model.js";

const apply = process.argv.includes("--apply");
const confirmed = process.argv.includes("--confirm-deduplicate-reviews");

if (apply && !confirmed) {
  console.error(
    "Refusing to modify data without --confirm-deduplicate-reviews"
  );
  process.exit(2);
}

if (!process.env.MONGODB_URL) {
  console.error("MONGODB_URL is required");
  process.exit(2);
}

try {
  mongoose.set("strictQuery", false);
  await mongoose.connect(process.env.MONGODB_URL);

  const duplicateGroups = await reviewModel.aggregate([
    {
      $group: {
        _id: {
          user: "$user",
          mediaType: "$mediaType",
          mediaId: "$mediaId",
        },
        count: { $sum: 1 },
        reviewIds: { $push: "$_id" },
      },
    },
    { $match: { count: { $gt: 1 } } },
  ]);

  const duplicateReviews = [];
  for (const group of duplicateGroups) {
    const reviews = await reviewModel
      .find({ _id: { $in: group.reviewIds } })
      .sort({ updatedAt: -1, createdAt: -1, _id: -1 })
      .lean();
    duplicateReviews.push({ keep: reviews[0], remove: reviews.slice(1) });
  }

  const removeCount = duplicateReviews.reduce(
    (total, group) => total + group.remove.length,
    0
  );
  console.log(
    JSON.stringify(
      {
        mode: apply ? "apply" : "dry-run",
        duplicateGroups: duplicateReviews.length,
        reviewsToRemove: removeCount,
      },
      null,
      2
    )
  );

  if (apply && removeCount > 0) {
    const backupDirectory = path.resolve("migration-backups");
    await fs.mkdir(backupDirectory, { recursive: true });
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const backupPath = path.join(
      backupDirectory,
      `review-duplicates-${timestamp}.json`
    );
    await fs.writeFile(
      backupPath,
      JSON.stringify(duplicateReviews, null, 2),
      { flag: "wx", mode: 0o600 }
    );

    const idsToRemove = duplicateReviews.flatMap((group) =>
      group.remove.map((review) => review._id)
    );
    const result = await reviewModel.deleteMany({ _id: { $in: idsToRemove } });
    console.log(
      JSON.stringify({ backupPath, removed: result.deletedCount }, null, 2)
    );
  }
} catch (error) {
  console.error("Review deduplication failed", {
    name: error.name,
    code: error.code,
  });
  process.exitCode = 1;
} finally {
  await mongoose.disconnect();
}
