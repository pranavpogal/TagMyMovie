import { LoadingButton } from "@mui/lab";
import {
  Box,
  Button,
  Divider,
  Rating,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import SendOutlinedIcon from "@mui/icons-material/SendOutlined";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import SaveIcon from "@mui/icons-material/Save";
import { toast } from "react-toastify";
import dayjs from "dayjs";
import { useSelector } from "react-redux";
import Container from "./Container";
import reviewApi from "../../api/modules/review.api";
import TextAvatar from "./TextAvatar";

const ratingLabel = (value) => `${value} out of 10`;

const ReviewItem = ({ review, onRemoved, onUpdated }) => {
  const { user } = useSelector((state) => state.user);

  const [onRequest, setOnRequest] = useState(false);
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(review.content || "");
  const [rating, setRating] = useState(review.rating ?? null);

  const onRemove = async () => {
    if (onRequest) return;
    setOnRequest(true);

    const { response, err } = await reviewApi.remove({ reviewId: review.id });
    setOnRequest(false);

    if (err) return toast.error(err.message);
    if (response) onRemoved(review.id);
  };

  const onUpdate = async () => {
    if (!content.trim() && rating === null) {
      return toast.error("Add review text or a rating");
    }

    setOnRequest(true);
    const { response, err } = await reviewApi.update({
      reviewId: review.id,
      content,
      rating,
    });
    setOnRequest(false);

    if (err) return toast.error(err.message);
    if (response) {
      onUpdated(response);
      setEditing(false);
      toast.success("Review updated");
    }
  };

  return (
    <Box
      sx={{
        padding: 2,
        borderRadius: "5px",
        position: "relative",
        opacity: onRequest ? 0.6 : 1,
        "&:hover": { backgroundColor: "background.paper" },
      }}
    >
      <Stack direction="row" spacing={2}>
        {/* avatar */}
        <TextAvatar text={review.user.displayName} />
        {/* avatar */}
        <Stack spacing={2} flexGrow={1}>
          <Stack spacing={1}>
            <Typography variant="h6" fontWeight="700">
              {review.user.displayName}
            </Typography>
            <Typography variant="caption">
              {dayjs(review.createdAt).format("DD-MM-YYYY HH:mm:ss")}
            </Typography>
          </Stack>
          {editing ? (
            <Stack spacing={2}>
              <Rating
                name={`edit-rating-${review.id}`}
                value={rating}
                onChange={(_, value) => setRating(value)}
                precision={0.5}
                max={10}
                getLabelText={ratingLabel}
              />
              <TextField
                value={content}
                onChange={(event) => setContent(event.target.value)}
                multiline
                minRows={3}
                inputProps={{ maxLength: 2000 }}
                label="Review (optional when rated)"
              />
              <Stack direction="row" spacing={1}>
                <LoadingButton
                  variant="contained"
                  startIcon={<SaveIcon />}
                  onClick={onUpdate}
                  loading={onRequest}
                >
                  save
                </LoadingButton>
                <Button
                  onClick={() => {
                    setContent(review.content || "");
                    setRating(review.rating ?? null);
                    setEditing(false);
                  }}
                >
                  cancel
                </Button>
              </Stack>
            </Stack>
          ) : (
            <>
              {review.rating !== null && review.rating !== undefined && (
                <Stack direction="row" spacing={1} alignItems="center">
                  <Rating
                    value={review.rating}
                    precision={0.5}
                    max={10}
                    readOnly
                    getLabelText={ratingLabel}
                  />
                  <Typography variant="body2">{review.rating}/10</Typography>
                </Stack>
              )}
              {review.content && (
                <Typography variant="body1" textAlign="justify">
                  {review.content}
                </Typography>
              )}
            </>
          )}
          {user && user.id === review.user.id && (
            <Stack direction="row" spacing={1} sx={{ width: "max-content" }}>
              {!editing && (
                <Button
                  variant="outlined"
                  startIcon={<EditIcon />}
                  onClick={() => setEditing(true)}
                >
                  edit
                </Button>
              )}
              <LoadingButton
                variant="contained"
                startIcon={<DeleteIcon />}
                onClick={onRemove}
                loading={onRequest}
                loadingPosition="start"
              >
                remove
              </LoadingButton>
            </Stack>
          )}
        </Stack>
      </Stack>
    </Box>
  );
};

const MediaReview = ({ reviews, media, mediaType }) => {
  const { user } = useSelector((state) => state.user);
  const [listReviews, setListReviews] = useState([]);
  const [filteredReviews, setFilteredReviews] = useState([]);
  const [page, setPage] = useState(1);
  const [onRequest, setOnRequest] = useState(false);
  const [content, setContent] = useState("");
  const [rating, setRating] = useState(null);
  const [reviewCount, setReviewCount] = useState(0);

  const skip = 4;

  useEffect(() => {
    const safeReviews = reviews || [];
    setListReviews([...safeReviews]);
    setFilteredReviews([...safeReviews].slice(0, skip));
    setReviewCount(safeReviews.length);
  }, [reviews]);

  const onAddReview = async () => {
    if (onRequest) return;
    if (!content.trim() && rating === null) {
      return toast.error("Add review text or a rating");
    }
    setOnRequest(true);

    const body = {
      content,
      mediaId: media.id,
      mediaType,
      mediaTitle: media.title || media.name,
      mediaPoster: media.poster_path,
      rating,
    };

    const { response, err } = await reviewApi.add(body);
    setOnRequest(false);

    if (err) toast.error(err.message);
    if (response) {
      toast.success("Review added");
      setFilteredReviews([response, ...filteredReviews]);
      setListReviews([response, ...listReviews]);
      setReviewCount(reviewCount + 1);
      setContent("");
      setRating(null);
    }
  };

  const onUpdated = (updatedReview) => {
    const updateReview = (review) =>
      review.id === updatedReview.id ? updatedReview : review;
    setListReviews((current) => current.map(updateReview));
    setFilteredReviews((current) => current.map(updateReview));
  };

  const hasCurrentUserReview =
    user && listReviews.some((review) => review.user?.id === user.id);

  const onLoadMore = () => {
    setFilteredReviews([
      ...filteredReviews,
      ...[...listReviews].splice(page * skip, skip),
    ]);
    const next = page + 1;
    setPage(next);
  };

  const onRemoved = (id) => {
    if (listReviews.findIndex((e) => e.id === id) !== -1) {
      const newListReviews = [...listReviews].filter((e) => e.id !== id);
      setListReviews(newListReviews);
    }

    setFilteredReviews([...filteredReviews].filter((e) => e.id !== id));

    setReviewCount(reviewCount - 1);

    toast.success("Review removed successfully");
  };

  return (
    <>
      <Container header={`Reviews ${reviewCount}`}>
        <Stack spacing={4} marginBottom={2}>
          {filteredReviews.map((item) => (
            <Box key={item.id}>
              <ReviewItem
                review={item}
                onRemoved={onRemoved}
                onUpdated={onUpdated}
              />
              <Divider
                sx={{
                  display: { xs: "block", md: "none" },
                }}
              />
            </Box>
          ))}
          {filteredReviews.length < listReviews.length && (
            <Button onClick={onLoadMore}>Load More</Button>
          )}
        </Stack>
        {user && !hasCurrentUserReview && (
          <>
            <Divider />
            <Stack spacing={2} direction="row">
              <TextAvatar text={user.displayName} />
              <Stack spacing={2} flexGrow={1}>
                <Typography variant="h6" fontWeight="700">
                  {user.displayName}
                </Typography>
                <Stack spacing={0.5}>
                  <Typography component="label" htmlFor="new-review-rating">
                    Your rating (optional)
                  </Typography>
                  <Rating
                    id="new-review-rating"
                    name="new-review-rating"
                    value={rating}
                    onChange={(_, value) => setRating(value)}
                    precision={0.5}
                    max={10}
                    getLabelText={ratingLabel}
                  />
                </Stack>
                <TextField
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  multiline
                  rows={4}
                  placeholder="Write your review"
                  variant="outlined"
                  label="Review (optional when rated)"
                  inputProps={{ maxLength: 2000 }}
                />
                <LoadingButton
                  variant="contained"
                  onClick={onAddReview}
                  loading={onRequest}
                  loadingPosition="start"
                  startIcon={<SendOutlinedIcon />}
                  size="large"
                  sx={{ width: "max-content" }}
                >
                  post
                </LoadingButton>
              </Stack>
            </Stack>
          </>
        )}
      </Container>
    </>
  );
};

export default MediaReview;
