import axiosClient from "../axios/axios.client.js";
import tmdbEndpoints from "./tmdb.endpoints.js";
import fs from "fs";
import path from "path";

const cacheDir = path.join(process.cwd(), "cache");

const tryLoadFromCache = (filename) => {
    try {
        const file = path.join(cacheDir, filename);
        if (fs.existsSync(file)) {
            const data = fs.readFileSync(file, 'utf8');
            return JSON.parse(data);
        }
    } catch (e) {
        console.error(`Error loading from cache: ${filename}`, e);
    }
    return null;
}

const tmdbApi = {
    mediaList: async ({ mediaType, mediaCategory, page }) => {
        const cacheKey = `${mediaType}-${mediaCategory}-${page}.json`;
        const cachedData = tryLoadFromCache(cacheKey);
        if (cachedData) return cachedData;
        return await axiosClient.get(
            tmdbEndpoints.mediaList({ mediaType, mediaCategory, page })
        );
    },
    mediaDetail: async ({ mediaType, mediaId }) => {
        const cacheKey = `${mediaType}-${mediaId}.json`;
        const cachedData = tryLoadFromCache(cacheKey);
        if (cachedData) return cachedData;
        return await axiosClient.get(tmdbEndpoints.mediaDetail({ mediaType, mediaId }));
    },
    mediaGenres: async ({ mediaType }) => {
        const cacheKey = `genre-${mediaType}-list.json`;
        const cachedData = tryLoadFromCache(cacheKey);
        if (cachedData) return cachedData;
        return await axiosClient.get(tmdbEndpoints.mediaGenres({ mediaType }));
    },
    mediaCredits: async ({ mediaType, mediaId }) => {
        const cacheKey = `${mediaType}-${mediaId}-credits.json`;
        const cachedData = tryLoadFromCache(cacheKey);
        if (cachedData) return cachedData;
        return await axiosClient.get(tmdbEndpoints.mediaCredits({ mediaType, mediaId }));
    },
    mediaVideos: async ({ mediaType, mediaId }) => {
        const cacheKey = `${mediaType}-${mediaId}-videos.json`;
        const cachedData = tryLoadFromCache(cacheKey);
        if (cachedData) return cachedData;
        return await axiosClient.get(tmdbEndpoints.mediaVideos({ mediaType, mediaId }))
    },
    mediaImages: async ({ mediaType, mediaId }) => {
        const cacheKey = `${mediaType}-${mediaId}-images.json`;
        const cachedData = tryLoadFromCache(cacheKey);
        if (cachedData) return cachedData;
        return await axiosClient.get(tmdbEndpoints.mediaImages({ mediaType, mediaId }))
    },
    mediaRecommend: async ({ mediaType, mediaId }) => {
        const cacheKey = `${mediaType}-${mediaId}-recommendations.json`;
        const cachedData = tryLoadFromCache(cacheKey);
        if (cachedData) return cachedData;
        return await axiosClient.get(tmdbEndpoints.mediaRecommend({ mediaType, mediaId }))
    },
    mediaSearch: async ({ mediaType, query, page }) =>
        await axiosClient.get(
            tmdbEndpoints.mediaSearch({ mediaType, query, page })
        ),
    personDetail: async ({ personId }) =>
        await axiosClient.get(tmdbEndpoints.personDetail({ personId })),
    personMedias: async ({ personId }) =>
        await axiosClient.get(tmdbEndpoints.personMedias({ personId })),
};

export default tmdbApi;
