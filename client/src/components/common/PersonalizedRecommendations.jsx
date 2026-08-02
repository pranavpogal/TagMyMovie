import BlockOutlinedIcon from "@mui/icons-material/BlockOutlined";
import { Alert, Box, Button, Card, CardContent, Chip, Skeleton, Snackbar, Stack, Typography } from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import { SwiperSlide } from "swiper/react";
import interactionApi from "../../api/modules/interaction.api";
import recommendationApi from "../../api/modules/recommendation.api";
import AutoSwiper from "./AutoSwiper";
import MediaItem from "./MediaItem";

const toMedia = (item) => ({
  ...item,
  id: item.mediaId,
  poster_path: item.posterPath,
  vote_average: item.voteAverage,
  release_date: item.releaseYear ? `${item.releaseYear}-01-01` : "",
  first_air_date: item.releaseYear ? `${item.releaseYear}-01-01` : "",
});

const LoadingCards = () => (
  <Stack direction="row" spacing={2} overflow="hidden">
    {[0, 1, 2, 3, 4].map((item) => (
      <Skeleton key={item} variant="rounded" sx={{ minWidth: { xs: 150, md: 210 }, height: { xs: 280, md: 360 } }} />
    ))}
  </Stack>
);

const PersonalizedRecommendations = ({ context = "home", seedMediaId, seedMediaType, excludeIds = [], onUnavailable }) => {
  const [batch, setBatch] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [hidden, setHidden] = useState([]);
  const [undoItem, setUndoItem] = useState(null);
  const excluded = useMemo(() => new Set(excludeIds.map(String)), [excludeIds]);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError(false);
      const { response } = await recommendationApi.get({ context, seedMediaId, seedMediaType, limit: 20 });
      if (!active) return;
      if (response) setBatch(response);
      else {
        setError(true);
        onUnavailable?.();
      }
      setLoading(false);
    };
    load();
    return () => { active = false; };
  }, [context, seedMediaId, seedMediaType, onUnavailable]);

  const items = (batch?.results || []).filter(
    (item) => !hidden.includes(`${item.mediaType}:${item.mediaId}`) && !excluded.has(String(item.mediaId))
  );

  const recordClick = (item, rank) => {
    interactionApi.record({
      mediaId: item.mediaId,
      mediaType: item.mediaType,
      eventType: "recommendation_click",
      recommendationId: batch.recommendationId,
      recommendationStrategy: batch.strategy,
      recommendationRank: rank,
      metadata: { context },
    });
  };

  const dismiss = async (event, item, rank) => {
    event.preventDefault();
    event.stopPropagation();
    const key = `${item.mediaType}:${item.mediaId}`;
    setHidden((current) => [...current, key]);
    const { err } = await interactionApi.record({
      mediaId: item.mediaId,
      mediaType: item.mediaType,
      eventType: "not_interested",
      recommendationId: batch.recommendationId,
      recommendationStrategy: batch.strategy,
      recommendationRank: rank,
      metadata: { context },
    });
    if (err) setHidden((current) => current.filter((entry) => entry !== key));
    else setUndoItem({ key, title: item.title });
  };

  if (loading) return <LoadingCards />;
  if (error && onUnavailable) return null;
  if (error) return <Alert severity="info">Personalized recommendations are unavailable right now.</Alert>;
  if (!items.length) return <Alert severity="info">Rate, favourite, or explore more titles to improve your recommendations.</Alert>;

  return (
    <>
      <AutoSwiper>
        {items.map((item, index) => (
          <SwiperSlide key={`${item.mediaType}:${item.mediaId}`}>
            <Card variant="outlined" sx={{ bgcolor: "transparent", height: "100%" }}>
              <MediaItem media={toMedia(item)} mediaType={item.mediaType} onClick={() => recordClick(item, index + 1)} />
              <CardContent sx={{ px: 1, pb: "8px !important" }}>
                <Stack spacing={1}>
                  <Typography variant="caption" sx={{ minHeight: 36 }}>
                    {(item.reasons || ["Picked for you"]).slice(0, 2).join(" · ")}
                  </Typography>
                  <Box><Chip size="small" label={batch.strategy?.replaceAll("_", " ") || "personalized"} /></Box>
                  <Button size="small" color="inherit" startIcon={<BlockOutlinedIcon />} onClick={(event) => dismiss(event, item, index + 1)}>
                    Not interested
                  </Button>
                </Stack>
              </CardContent>
            </Card>
          </SwiperSlide>
        ))}
      </AutoSwiper>
      <Snackbar
        open={Boolean(undoItem)}
        autoHideDuration={6000}
        message={`${undoItem?.title || "Title"} hidden for this session`}
        action={<Button color="secondary" size="small" onClick={() => { setHidden((current) => current.filter((key) => key !== undoItem.key)); setUndoItem(null); }}>Undo</Button>}
        onClose={() => setUndoItem(null)}
      />
    </>
  );
};

export default PersonalizedRecommendations;
