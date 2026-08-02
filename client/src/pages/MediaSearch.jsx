import { LoadingButton } from "@mui/lab";
import { Alert, Box, Button, Chip, FormControl, InputLabel, MenuItem, Select, Stack, TextField, Toolbar } from "@mui/material";
import { useCallback, useEffect, useState } from "react";
import { useSelector } from "react-redux";
import { toast } from "react-toastify";
import genreApi from "../api/modules/genre.api";
import interactionApi from "../api/modules/interaction.api";
import mediaApi from "../api/modules/media.api";
import MediaGrid from "../components/common/MediaGrid";
import uiConfigs from "../configs/ui.configs";

const keywordMediaTypes = ["movie", "tv", "people"];
const semanticMediaTypes = ["movie", "tv"];
const languages = [{ code: "", label: "Any language" }, { code: "en", label: "English" },
  { code: "hi", label: "Hindi" }, { code: "mr", label: "Marathi" },
  { code: "ta", label: "Tamil" }, { code: "te", label: "Telugu" },
  { code: "es", label: "Spanish" }, { code: "fr", label: "French" },
  { code: "ja", label: "Japanese" }, { code: "ko", label: "Korean" }];
let timer;
const timeout = 500;

const normalizeSemanticMedia = (media) => ({
  ...media,
  id: media.mediaId,
  poster_path: media.posterPath,
  vote_average: media.voteAverage,
  release_date: media.releaseYear ? `${media.releaseYear}-01-01` : "",
  first_air_date: media.releaseYear ? `${media.releaseYear}-01-01` : "",
});

const MediaSearch = () => {
  const { user } = useSelector((state) => state.user);
  const [medias, setMedias] = useState([]);
  const [page, setPage] = useState(1);
  const [onSearch, setOnSearch] = useState(false);
  const [query, setQuery] = useState("");
  const [input, setInput] = useState("");
  const [mediaType, setMediaType] = useState("movie");
  const [searchMode, setSearchMode] = useState("keyword");
  const [language, setLanguage] = useState("");
  const [genreIds, setGenreIds] = useState([]);
  const [genres, setGenres] = useState([]);
  const [hasSearched, setHasSearched] = useState(false);

  const keywordSearch = useCallback(async () => {
    if (!query) return;
    setOnSearch(true);
    const { response, err } = await mediaApi.search({ mediaType, query, page });
    setOnSearch(false);
    if (err) return toast.error(err.message);
    if (response) {
      if (page === 1) setMedias(response.results || []);
      else setMedias((current) => [...current, ...(response.results || [])]);
    }
  }, [mediaType, query, page]);

  useEffect(() => {
    if (searchMode !== "keyword") return;
    if (!query) { setMedias([]); setPage(1); }
    else keywordSearch();
  }, [keywordSearch, query, searchMode]);

  useEffect(() => {
    if (searchMode !== "semantic") return;
    genreApi.getList({ mediaType }).then(({ response }) => setGenres(response?.genres || []));
  }, [searchMode, mediaType]);

  const semanticSearch = async () => {
    const text = input.trim();
    if (text.length < 2) return toast.error("Describe what you want to watch");
    setOnSearch(true);
    setHasSearched(true);
    const { response, err } = await mediaApi.semanticSearch({ mediaType, query: text, language, genreIds });
    setOnSearch(false);
    if (err) return toast.error(err.message || "Semantic search is unavailable");
    setMedias((response?.results || []).map(normalizeSemanticMedia));
  };

  const changeMode = (mode) => {
    setSearchMode(mode);
    setMediaType("movie");
    setMedias([]);
    setPage(1);
    setHasSearched(false);
  };

  const onQueryChange = (event) => {
    const value = event.target.value;
    setInput(value);
    if (searchMode === "semantic") return;
    clearTimeout(timer);
    timer = setTimeout(() => setQuery(value.trim()), timeout);
  };

  const onMediaClick = (media) => {
    if (!user || mediaType === "people") return;
    interactionApi.record({
      mediaId: media.id || media.mediaId,
      mediaType,
      eventType: "search_click",
      metadata: { searchType: searchMode },
    });
  };

  const availableTypes = searchMode === "semantic" ? semanticMediaTypes : keywordMediaTypes;

  return (
    <>
      <Toolbar />
      <Box sx={{ ...uiConfigs.style.mainContent }}>
        <Stack spacing={2}>
          <Stack direction="row" spacing={1} justifyContent="center">
            <Button size="large" variant={searchMode === "keyword" ? "contained" : "outlined"} onClick={() => changeMode("keyword")}>TMDB keyword search</Button>
            <Button size="large" variant={searchMode === "semantic" ? "contained" : "outlined"} onClick={() => changeMode("semantic")}>Semantic search</Button>
          </Stack>
          {searchMode === "semantic" && <Alert severity="info">Semantic search uses ML to match the meaning and mood of your description.</Alert>}
          <Stack direction="row" spacing={2} justifyContent="center">
            {availableTypes.map((type) => <Button key={type} size="large" variant={mediaType === type ? "contained" : "text"} onClick={() => { setMediaType(type); setMedias([]); setPage(1); }}>{type}</Button>)}
          </Stack>
          {searchMode === "semantic" && (
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <FormControl sx={{ minWidth: 180 }}><InputLabel>Language</InputLabel><Select value={language} label="Language" onChange={(event) => setLanguage(event.target.value)}>{languages.map((item) => <MenuItem key={item.code} value={item.code}>{item.label}</MenuItem>)}</Select></FormControl>
              <FormControl fullWidth><InputLabel>Genres</InputLabel><Select multiple value={genreIds} label="Genres" onChange={(event) => setGenreIds(event.target.value)} renderValue={(selected) => <Stack direction="row" gap={0.5} flexWrap="wrap">{selected.map((id) => <Chip key={id} size="small" label={genres.find((genre) => genre.id === id)?.name || id} />)}</Stack>}>{genres.map((genre) => <MenuItem key={genre.id} value={genre.id}>{genre.name}</MenuItem>)}</Select></FormControl>
            </Stack>
          )}
          <Stack direction="row" spacing={1}>
            <TextField fullWidth placeholder={searchMode === "semantic" ? "e.g. A dark investigative thriller with little action" : "Search TagMyMovie"} value={input} onChange={onQueryChange} onKeyDown={(event) => { if (event.key === "Enter" && searchMode === "semantic") semanticSearch(); }} autoFocus />
            {searchMode === "semantic" && <LoadingButton loading={onSearch} variant="contained" onClick={semanticSearch}>Search</LoadingButton>}
          </Stack>
          <MediaGrid medias={medias} mediaType={mediaType} onMediaClick={onMediaClick} />
          {searchMode === "semantic" && hasSearched && !onSearch && medias.length === 0 && <Alert severity="info">No semantic matches found. Try a broader description or fewer filters.</Alert>}
          {searchMode === "keyword" && medias.length > 0 && <LoadingButton loading={onSearch} onClick={() => setPage((current) => current + 1)}>Load More</LoadingButton>}
        </Stack>
      </Box>
    </>
  );
};

export default MediaSearch;
