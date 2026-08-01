import { SwiperSlide } from "swiper/react";
import AutoSwiper from "./AutoSwiper";
import MediaItem from "./MediaItem";

const RecommendSlide = ({ medias, mediaType, onMediaClick }) => {
  return (
    <AutoSwiper>
      {medias.map((item, index) => (
        <SwiperSlide key={item.id || index}>
          <MediaItem
            media={item}
            mediaType={mediaType}
            onClick={() => onMediaClick?.(item, index + 1)}
          />
        </SwiperSlide>
      ))}
    </AutoSwiper>
  );
};

export default RecommendSlide;
