/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  FEATURE · Stream & Video Player                                    │
 * │  Category : feature (video playback state, episode/season tracking) │
 * │  Tests    : 27                                                      │
 * │  Sources  :                                                         │
 * │    src/reducer/streamReducer.js   (streamReducer)                   │
 * │    src/reducer/videoDetails.js    (videoDetails)                    │
 * │    src/reducer/actiotypes.js      (action type strings)             │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     stream-video-feature
 * @category  feature
 * @sources   src/reducer/streamReducer.js,
 *            src/reducer/videoDetails.js,
 *            src/reducer/actiotypes.js
 */

// ── Inlined from src/reducer/actiotypes.js ───────────────────────────────────
const STREAMEDMOVIEINFO      = 'STREAMEDMOVIEINFO';
const STREAMEDEPISODEINFO    = 'STREAMEDEPISODEINFO';
const STREAMSEASONINFO       = 'STREAMSEASONINFO';
const STREAMINGVIDEOURL      = 'STREAMINGVIDEOURL';
const SETACTIVEEPISODEINDEX  = 'SETACTIVEEPISODEINDEX';
const SETACTIVESEASONINDEX   = 'SETACTIVESEASONINDEX';
const UPCOMINGEPISODES       = 'UPCOMINGEPISODES';
const VIDEOBUFFERING         = 'VIDEOBUFFERING';
const STREAMEDSUBTITLES      = 'STREAMEDSUBTITLES';
const ACTIVESUBTITLE         = 'ACTIVESUBTITLE';
const SET_VIDEO_PLAYER_STATE = 'SET_VIDEO_PLAYER_STATE';
const VIDEO_PLAYED_UPTO      = 'VIDEO_PLAYED_UPTO';
const VIDEODETAILS           = 'VIDEODETAILS';
const PIPSTATUS              = 'PIPSTATUS';
const PIPIDSTATUS            = 'PIPIDSTATUS';

// ── Inlined from src/reducer/streamReducer.js ────────────────────────────────
/** @symbol streamReducer  @source src/reducer/streamReducer.js */
const streamInitialState = {
  streamingID:         '',
  movieDetails:        undefined,
  episodeDetails:      undefined,
  seasonDetails:       undefined,
  videoURL:            undefined,
  activeEpisodeIndex:  0,
  totalSeasonIndex:    0,
  totalEpisodeIndex:   0,
  activeSeasonIndex:   0,
  nextPlaybackEpisodes:undefined,
  onBufferSpinner:     false,
  subTitles:           undefined,
  videoPlayerLoading:  false,
  videoPlayedUpto:     0,
  activeSubTitle:      '',
};

function streamReducer(state = streamInitialState, action) {
  switch (action.type) {
    case STREAMEDMOVIEINFO:
      return { ...state, movieDetails: action.movie, streamingID: action.id };
    case STREAMEDEPISODEINFO:
      return {
        ...state,
        episodeDetails:    action.episode,
        totalEpisodeIndex:
          action?.episode !== undefined && action?.episode.length !== undefined
            ? action?.episode.length : 0,
      };
    case STREAMSEASONINFO:
      return {
        ...state,
        seasonDetails:   action.season,
        totalSeasonIndex:
          action?.season !== undefined && action?.season.length !== undefined
            ? action?.season.length : 0,
      };
    case STREAMINGVIDEOURL:
      return { ...state, videoURL: action.videoURL };
    case SETACTIVEEPISODEINDEX:
      return { ...state, activeEpisodeIndex: action.activeIndex };
    case SETACTIVESEASONINDEX:
      return { ...state, activeSeasonIndex: action.ID };
    case ACTIVESUBTITLE:
      return { ...state, activeSubTitle: action.title };
    case UPCOMINGEPISODES:
      return { ...state, nextPlaybackEpisodes: action.upcomingEpisodes };
    case VIDEOBUFFERING:
      return { ...state, onBufferSpinner: action.onBuffer };
    case STREAMEDSUBTITLES:
      return { ...state, subTitles: action.subTitlesArr };
    case SET_VIDEO_PLAYER_STATE:
      return { ...state, videoPlayerLoading: action.data };
    case VIDEO_PLAYED_UPTO:
      return { ...state, videoPlayedUpto: action.data };
    default:
      return state;
  }
}

// ── Inlined from src/reducer/videoDetails.js ─────────────────────────────────
/** @symbol videoDetails  @source src/reducer/videoDetails.js */
const videoInitialState = {
  videoListData: {},
  pipStatus:     false,
  videoId:       null,
};

const videoDetails = (state = videoInitialState, action) => {
  switch (action.type) {
    case VIDEODETAILS:
      return { ...state, videoListData: action.data };
    case PIPSTATUS:
      return { ...state, pipStatus: action.data };
    case PIPIDSTATUS:
      return { ...state, videoId: action.videoId };
    default:
      return state;
  }
};

// ─────────────────────────────────────────────────────────────────────────────

/**
 * @source src/reducer/streamReducer.js
 * @symbol streamReducer
 */
describe('streamReducer', () => {
  it('initialises with an empty streamingID string', () => {
    const state = streamReducer(undefined, { type: '@@INIT' });
    expect(state.streamingID).toBe('');
  });

  it('initialises with videoURL as undefined', () => {
    const state = streamReducer(undefined, { type: '@@INIT' });
    expect(state.videoURL).toBeUndefined();
  });

  it('initialises with activeEpisodeIndex as 0', () => {
    const state = streamReducer(undefined, { type: '@@INIT' });
    expect(state.activeEpisodeIndex).toBe(0);
  });

  it('initialises with onBufferSpinner as false', () => {
    const state = streamReducer(undefined, { type: '@@INIT' });
    expect(state.onBufferSpinner).toBe(false);
  });

  it('initialises with videoPlayerLoading as false', () => {
    const state = streamReducer(undefined, { type: '@@INIT' });
    expect(state.videoPlayerLoading).toBe(false);
  });

  it('initialises with videoPlayedUpto as 0', () => {
    const state = streamReducer(undefined, { type: '@@INIT' });
    expect(state.videoPlayedUpto).toBe(0);
  });

  it('STREAMEDMOVIEINFO stores movie details and streamingID', () => {
    const movie = { title: 'Avengers', duration: 180 };
    const state = streamReducer(undefined, { type: STREAMEDMOVIEINFO, movie, id: 'movie-42' });
    expect(state.movieDetails).toEqual(movie);
    expect(state.streamingID).toBe('movie-42');
  });

  it('STREAMEDEPISODEINFO stores episode list and sets totalEpisodeIndex', () => {
    const episodes = [{ ep: 1 }, { ep: 2 }, { ep: 3 }];
    const state = streamReducer(undefined, { type: STREAMEDEPISODEINFO, episode: episodes });
    expect(state.episodeDetails).toEqual(episodes);
    expect(state.totalEpisodeIndex).toBe(3);
  });

  it('STREAMEDEPISODEINFO sets totalEpisodeIndex to 0 when episode is undefined', () => {
    const state = streamReducer(undefined, { type: STREAMEDEPISODEINFO, episode: undefined });
    expect(state.totalEpisodeIndex).toBe(0);
  });

  it('STREAMSEASONINFO stores season list and sets totalSeasonIndex', () => {
    const seasons = [{ season: 1 }, { season: 2 }];
    const state = streamReducer(undefined, { type: STREAMSEASONINFO, season: seasons });
    expect(state.seasonDetails).toEqual(seasons);
    expect(state.totalSeasonIndex).toBe(2);
  });

  it('STREAMINGVIDEOURL stores the video URL', () => {
    const url = 'https://cdn.example.com/stream/movie42.m3u8';
    const state = streamReducer(undefined, { type: STREAMINGVIDEOURL, videoURL: url });
    expect(state.videoURL).toBe(url);
  });

  it('SETACTIVEEPISODEINDEX updates activeEpisodeIndex', () => {
    const state = streamReducer(undefined, { type: SETACTIVEEPISODEINDEX, activeIndex: 4 });
    expect(state.activeEpisodeIndex).toBe(4);
  });

  it('SETACTIVESEASONINDEX updates activeSeasonIndex', () => {
    const state = streamReducer(undefined, { type: SETACTIVESEASONINDEX, ID: 2 });
    expect(state.activeSeasonIndex).toBe(2);
  });

  it('VIDEOBUFFERING sets onBufferSpinner to true when buffering', () => {
    const state = streamReducer(undefined, { type: VIDEOBUFFERING, onBuffer: true });
    expect(state.onBufferSpinner).toBe(true);
  });

  it('VIDEOBUFFERING sets onBufferSpinner to false when buffering ends', () => {
    const buffering = streamReducer(undefined, { type: VIDEOBUFFERING, onBuffer: true });
    const done      = streamReducer(buffering,  { type: VIDEOBUFFERING, onBuffer: false });
    expect(done.onBufferSpinner).toBe(false);
  });

  it('STREAMEDSUBTITLES stores the subtitles array', () => {
    const subs = [{ language: 'English' }, { language: 'Spanish' }];
    const state = streamReducer(undefined, { type: STREAMEDSUBTITLES, subTitlesArr: subs });
    expect(state.subTitles).toEqual(subs);
  });

  it('ACTIVESUBTITLE stores the selected subtitle language', () => {
    const state = streamReducer(undefined, { type: ACTIVESUBTITLE, title: 'English' });
    expect(state.activeSubTitle).toBe('English');
  });

  it('UPCOMINGEPISODES stores the next playback episodes', () => {
    const upcoming = [{ ep: 4 }, { ep: 5 }];
    const state = streamReducer(undefined, { type: UPCOMINGEPISODES, upcomingEpisodes: upcoming });
    expect(state.nextPlaybackEpisodes).toEqual(upcoming);
  });

  it('SET_VIDEO_PLAYER_STATE sets videoPlayerLoading to true', () => {
    const state = streamReducer(undefined, { type: SET_VIDEO_PLAYER_STATE, data: true });
    expect(state.videoPlayerLoading).toBe(true);
  });

  it('VIDEO_PLAYED_UPTO stores the playback progress in seconds', () => {
    const state = streamReducer(undefined, { type: VIDEO_PLAYED_UPTO, data: 320 });
    expect(state.videoPlayedUpto).toBe(320);
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = streamReducer(undefined, { type: '@@INIT' });
    const after  = streamReducer(before,    { type: 'UNKNOWN_STREAM_ACTION' });
    expect(after).toEqual(before);
  });
});

/**
 * @source src/reducer/videoDetails.js
 * @symbol videoDetails
 */
describe('videoDetails reducer', () => {
  it('initialises with an empty videoListData object', () => {
    const state = videoDetails(undefined, { type: '@@INIT' });
    expect(state.videoListData).toEqual({});
  });

  it('initialises with pipStatus as false', () => {
    const state = videoDetails(undefined, { type: '@@INIT' });
    expect(state.pipStatus).toBe(false);
  });

  it('initialises with videoId as null', () => {
    const state = videoDetails(undefined, { type: '@@INIT' });
    expect(state.videoId).toBeNull();
  });

  it('VIDEODETAILS stores the video list data', () => {
    const data  = { id: 'v1', title: 'Fight Night', url: 'https://cdn.example.com/v1.m3u8' };
    const state = videoDetails(undefined, { type: VIDEODETAILS, data });
    expect(state.videoListData).toEqual(data);
  });

  it('PIPSTATUS sets pipStatus to true when PiP is active', () => {
    const state = videoDetails(undefined, { type: PIPSTATUS, data: true });
    expect(state.pipStatus).toBe(true);
  });

  it('PIPSTATUS sets pipStatus back to false when PiP is dismissed', () => {
    const active   = videoDetails(undefined, { type: PIPSTATUS, data: true });
    const inactive = videoDetails(active,    { type: PIPSTATUS, data: false });
    expect(inactive.pipStatus).toBe(false);
  });

  it('PIPIDSTATUS stores the video ID for picture-in-picture tracking', () => {
    const state = videoDetails(undefined, { type: PIPIDSTATUS, videoId: 'vid-99' });
    expect(state.videoId).toBe('vid-99');
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = videoDetails(undefined, { type: '@@INIT' });
    const after  = videoDetails(before,    { type: 'UNKNOWN_VIDEO_ACTION' });
    expect(after).toEqual(before);
  });
});
