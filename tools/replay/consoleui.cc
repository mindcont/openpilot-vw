#include "tools/replay/consoleui.h"

#include <time.h>
#include <initializer_list>
#include <string>
#include <tuple>
#include <utility>
#include <locale>
#include <clocale>
#include <wchar.h>
#include <ncursesw/ncurses.h>

#include "common/ratekeeper.h"
#include "common/util.h"
#include "common/version.h"

namespace {

const int BORDER_SIZE = 3;

// Language support
enum Language { EN, ZH };
static Language current_lang = EN;

struct LocalizedText {
  const char* en;
  const char* zh;
};

const char* getText(const LocalizedText& text) {
  return current_lang == ZH ? text.zh : text.en;
}

// Localized strings
const LocalizedText TITLE = {"openpilot replay", "openpilot 回放"};
const LocalizedText STATUS_PLAYING = {"playing", "播放中"};
const LocalizedText STATUS_PAUSED = {"paused...", "已暂停..."};
const LocalizedText ROUTE_TEXT = {"Route:", "路线:"};
const LocalizedText SEGMENTS_TEXT = {"segments", "段"};
const LocalizedText CAR_FINGERPRINT = {"Car Fingerprint:", "车辆指纹:"};
const LocalizedText STATUS_LABEL = {"STATUS:", "状态:"};
const LocalizedText TIME_LABEL = {"TIME:", "时间:"};
const LocalizedText STIFFNESS_LABEL = {"STIFFNESS:", "刚度:"};
const LocalizedText SPEED_LABEL = {"SPEED:", "速度:"};
const LocalizedText STEER_RATIO_LABEL = {"STEER RATIO:", "转向比:"};
const LocalizedText ANGLE_OFFSET_LABEL = {"ANGLE OFFSET(AVG|INSTANT):", "角度偏移(平均|瞬时):"};
const LocalizedText DOWNLOADING = {"Downloading", "下载中"};
const LocalizedText EXPAND_SCREEN = {"Expand screen vertically to list available commands", "垂直扩展屏幕以显示可用命令"};
const LocalizedText SEEK_REQUEST = {"Enter seek request:", "输入跳转请求:"};
const LocalizedText WAITING_INPUT = {"Waiting for input...", "等待输入..."};
const LocalizedText ENGAGED = {" Engaged ", " 已接管 "};
const LocalizedText DISENGAGED = {" Disengaged ", " 未接管 "};
const LocalizedText INFO_LABEL = {" Info ", " 信息 "};
const LocalizedText WARNING_LABEL = {" Warning ", " 警告 "};
const LocalizedText CRITICAL_LABEL = {" Critical ", " 严重 "};
const LocalizedText USER_TAG = {" User Tag ", " 用户标签 "};

const std::initializer_list<std::pair<std::string, LocalizedText>> keyboard_shortcuts[] = {
  {
    {"s", {"+10s", "+10秒"}},
    {"shift+s", {"-10s", "-10秒"}},
    {"m", {"+60s", "+60秒"}},
    {"shift+m", {"-60s", "-60秒"}},
    {"space", {"Pause/Resume", "暂停/继续"}},
    {"e", {"Next Engagement", "下一个接管"}},
    {"d", {"Next Disengagement", "下一个脱离"}},
    {"t", {"Next User Tag", "下一个用户标签"}},
    {"i", {"Next Info", "下一个信息"}},
    {"w", {"Next Warning", "下一个警告"}},
    {"c", {"Next Critical", "下一个严重"}},
  },
  {
    {"enter", {"Enter seek request", "输入跳转请求"}},
    {"+/-", {"Playback speed", "播放速度"}},
    {"l", {"Toggle Language", "切换语言"}},
    {"q", {"Exit", "退出"}},
  },
};

enum Color {
  Default,
  Debug,
  Yellow,
  Green,
  Red,
  Cyan,
  BrightWhite,
  Engaged,
  Disengaged,
};

void add_str(WINDOW *w, const char *str, Color color = Color::Default, bool bold = false) {
  if (color != Color::Default) wattron(w, COLOR_PAIR(color));
  if (bold) wattron(w, A_BOLD);
  
  // Convert UTF-8 string to wide characters for proper display
  size_t len = strlen(str);
  wchar_t *wstr = new wchar_t[len + 1];
  size_t wlen = mbstowcs(wstr, str, len);
  if (wlen != (size_t)-1) {
    wstr[wlen] = L'\0';
    waddwstr(w, wstr);
  } else {
    // Fallback to regular string if conversion fails
    waddstr(w, str);
  }
  delete[] wstr;
  
  if (bold) wattroff(w, A_BOLD);
  if (color != Color::Default) wattroff(w, COLOR_PAIR(color));
}

ExitHandler do_exit;

}  // namespace

ConsoleUI::ConsoleUI(Replay *replay) : replay(replay), sm({"carState", "liveParameters"}) {
  // Set locale for proper UTF-8 support
  setlocale(LC_ALL, "");
  setlocale(LC_CTYPE, "zh_CN.UTF-8");
  
  // Initialize curses with wide character support
  initscr();
  clear();
  curs_set(false);
  cbreak();  // Line buffering disabled. pass on everything
  noecho();
  keypad(stdscr, true);
  nodelay(stdscr, true);  // non-blocking getchar()

  // Initialize all the colors. https://www.ditig.com/256-colors-cheat-sheet
  start_color();
  init_pair(Color::Debug, 246, COLOR_BLACK);  // #949494
  init_pair(Color::Yellow, 184, COLOR_BLACK);
  init_pair(Color::Red, COLOR_RED, COLOR_BLACK);
  init_pair(Color::Cyan, COLOR_CYAN, COLOR_BLACK);
  init_pair(Color::BrightWhite, 15, COLOR_BLACK);
  init_pair(Color::Disengaged, COLOR_BLUE, COLOR_BLUE);
  init_pair(Color::Engaged, 28, 28);
  init_pair(Color::Green, 34, COLOR_BLACK);

  initWindows();

  installMessageHandler([this](ReplyMsgType type, const std::string msg) {
    std::scoped_lock lock(mutex);
    logs.emplace_back(type, msg);
  });
  installDownloadProgressHandler([this](uint64_t cur, uint64_t total, bool success) {
    std::scoped_lock lock(mutex);
    progress_cur = cur;
    progress_total = total;
    download_success = success;
  });
}

ConsoleUI::~ConsoleUI() {
  installDownloadProgressHandler(nullptr);
  installMessageHandler(nullptr);
  endwin();
}

void ConsoleUI::initWindows() {
  getmaxyx(stdscr, max_height, max_width);
  w.fill(nullptr);
  w[Win::Title] = newwin(1, max_width, 0, 0);
  w[Win::Stats] = newwin(2, max_width - 2 * BORDER_SIZE, 2, BORDER_SIZE);
  w[Win::Timeline] = newwin(4, max_width - 2 * BORDER_SIZE, 5, BORDER_SIZE);
  w[Win::TimelineDesc] = newwin(1, 100, 10, BORDER_SIZE);
  w[Win::CarState] = newwin(3, 100, 12, BORDER_SIZE);
  w[Win::DownloadBar] = newwin(1, 100, 16, BORDER_SIZE);
  if (int log_height = max_height - 27; log_height > 4) {
    w[Win::LogBorder] = newwin(log_height, max_width - 2 * (BORDER_SIZE - 1), 17, BORDER_SIZE - 1);
    box(w[Win::LogBorder], 0, 0);
    w[Win::Log] = newwin(log_height - 2, max_width - 2 * BORDER_SIZE, 18, BORDER_SIZE);
    scrollok(w[Win::Log], true);
  }
  if (max_height >= 23) {
    w[Win::Help] = newwin(5, max_width - (2 * BORDER_SIZE), max_height - 6, BORDER_SIZE);
  } else if (max_height >= 17) {
    w[Win::Help] = newwin(1, max_width - (2 * BORDER_SIZE), max_height - 1, BORDER_SIZE);
    mvwprintw(w[Win::Help], 0, 0, "%s", getText(EXPAND_SCREEN));
  }

  // set the title bar
  wbkgd(w[Win::Title], A_REVERSE);
  mvwprintw(w[Win::Title], 0, 3, "%s %s", getText(TITLE), COMMA_VERSION);

  // show windows on the real screen
  refresh();
  displayTimelineDesc();
  if (max_height >= 23) displayHelp();
  updateSummary();
  updateTimeline();
  for (auto win : w) {
    if (win) wrefresh(win);
  }
}

void ConsoleUI::updateSize() {
  if (is_term_resized(max_height, max_width)) {
    for (auto win : w) {
      if (win) delwin(win);
    }
    endwin();
    clear();
    refresh();
    initWindows();
    rWarning("resize term %dx%d", max_height, max_width);
  }
}

void ConsoleUI::updateStatus() {
  auto write_item = [this](int y, int x, const char *key, const std::string &value, const std::string &unit,
                           bool bold = false, Color color = Color::BrightWhite) {
    auto win = w[Win::CarState];
    wmove(win, y, x);
    add_str(win, key);
    add_str(win, value.c_str(), color, bold);
    add_str(win, unit.c_str());
  };
  static const std::pair<LocalizedText, Color> status_text[] = {
      {STATUS_PLAYING, Color::Green},
      {STATUS_PAUSED, Color::Yellow},
  };

  sm.update(0);

  auto [status_localized, status_color] = status_text[status];
  write_item(0, 0, getText(STATUS_LABEL), getText(status_localized), "      ", false, status_color);
  auto cur_ts = replay->routeDateTime() + (int)replay->currentSeconds();
  char *time_string = ctime(&cur_ts);
  std::string current_segment = " - " + std::to_string((int)(replay->currentSeconds() / 60));
  write_item(0, 25, getText(TIME_LABEL), time_string, current_segment, true);

  auto p = sm["liveParameters"].getLiveParameters();
  write_item(1, 0, getText(STIFFNESS_LABEL), util::string_format("%.2f %%", p.getStiffnessFactor() * 100), "  ");
  write_item(1, 25, getText(SPEED_LABEL), util::string_format("%.2f", sm["carState"].getCarState().getVEgo()), " m/s");
  write_item(2, 0, getText(STEER_RATIO_LABEL), util::string_format("%.2f", p.getSteerRatio()), "");
  auto angle_offsets = util::string_format("%.2f|%.2f", p.getAngleOffsetAverageDeg(), p.getAngleOffsetDeg());
  write_item(2, 25, getText(ANGLE_OFFSET_LABEL), angle_offsets, " deg");

  wrefresh(w[Win::CarState]);
}

void ConsoleUI::displayHelp() {
  werase(w[Win::Help]);  // Clear window before redrawing
  for (int i = 0; i < std::size(keyboard_shortcuts); ++i) {
    wmove(w[Win::Help], i * 2, 0);
    for (auto &[key, desc] : keyboard_shortcuts[i]) {
      wattron(w[Win::Help], A_REVERSE);
      std::string key_str = " " + key + " ";
      waddstr(w[Win::Help], key_str.c_str());
      wattroff(w[Win::Help], A_REVERSE);
      std::string desc_str = " " + std::string(getText(desc)) + " ";
      waddstr(w[Win::Help], desc_str.c_str());
    }
  }
  wrefresh(w[Win::Help]);
}

void ConsoleUI::displayTimelineDesc() {
  werase(w[Win::TimelineDesc]);  // Clear window before redrawing
  std::tuple<Color, LocalizedText, bool> indicators[]{
      {Color::Engaged, ENGAGED, false},
      {Color::Disengaged, DISENGAGED, false},
      {Color::Green, INFO_LABEL, true},
      {Color::Yellow, WARNING_LABEL, true},
      {Color::Red, CRITICAL_LABEL, true},
      {Color::Cyan, USER_TAG, true},
  };
  for (auto [color, name_text, bold] : indicators) {
    add_str(w[Win::TimelineDesc], "__", color, bold);
    add_str(w[Win::TimelineDesc], getText(name_text));
  }
  wrefresh(w[Win::TimelineDesc]);
}

void ConsoleUI::logMessage(ReplyMsgType type, const std::string &msg) {
  if (auto win = w[Win::Log]) {
    Color color = Color::Default;
    if (type == ReplyMsgType::Debug) {
      color = Color::Debug;
    } else if (type == ReplyMsgType::Warning) {
      color = Color::Yellow;
    } else if (type == ReplyMsgType::Critical) {
      color = Color::Red;
    }
    add_str(win, (msg + "\n").c_str(), color);
    wrefresh(win);
  }
}

void ConsoleUI::updateProgressBar() {
  werase(w[Win::DownloadBar]);
  if (download_success && progress_cur < progress_total) {
    const int width = 35;
    const float progress = progress_cur / (double)progress_total;
    const int pos = width * progress;
    wprintw(w[Win::DownloadBar], "%s [%s>%s]  %d%% %s", getText(DOWNLOADING), std::string(pos, '=').c_str(),
            std::string(width - pos, ' ').c_str(), int(progress * 100.0), formattedDataSize(progress_total).c_str());
  }
  wrefresh(w[Win::DownloadBar]);
}

void ConsoleUI::updateSummary() {
  const auto &route = replay->route();
  mvwprintw(w[Win::Stats], 0, 0, "%s %s, %lu %s", getText(ROUTE_TEXT), route.name().c_str(), route.segments().size(), getText(SEGMENTS_TEXT));
  mvwprintw(w[Win::Stats], 1, 0, "%s %s", getText(CAR_FINGERPRINT), replay->carFingerprint().c_str());
  wrefresh(w[Win::Stats]);
}

void ConsoleUI::updateTimeline() {
  auto win = w[Win::Timeline];
  int width = getmaxx(win);
  werase(win);

  wattron(win, COLOR_PAIR(Color::Disengaged));
  mvwhline(win, 1, 0, ' ', width);
  mvwhline(win, 2, 0, ' ', width);
  wattroff(win, COLOR_PAIR(Color::Disengaged));

  const int total_sec = replay->maxSeconds() - replay->minSeconds();
  for (const auto &entry : *replay->getTimeline()) {
    int start_pos = ((entry.start_time - replay->minSeconds()) / total_sec) * width;
    int end_pos = ((entry.end_time - replay->minSeconds()) / total_sec) * width;
    if (entry.type == TimelineType::Engaged) {
      mvwchgat(win, 1, start_pos, end_pos - start_pos + 1, A_COLOR, Color::Engaged, NULL);
      mvwchgat(win, 2, start_pos, end_pos - start_pos + 1, A_COLOR, Color::Engaged, NULL);
    } else if (entry.type == TimelineType::UserBookmark) {
      mvwchgat(win, 3, start_pos, end_pos - start_pos + 1, ACS_S3, Color::Cyan, NULL);
    } else {
      auto color_id = Color::Green;
      if (entry.type != TimelineType::AlertInfo) {
        color_id = entry.type == TimelineType::AlertWarning ? Color::Yellow : Color::Red;
      }
      mvwchgat(win, 3, start_pos, end_pos - start_pos + 1, ACS_S3, color_id, NULL);
    }
  }

  int cur_pos = ((replay->currentSeconds() - replay->minSeconds()) / total_sec) * width;
  wattron(win, COLOR_PAIR(Color::BrightWhite));
  mvwaddch(win, 0, cur_pos, ACS_VLINE);
  mvwaddch(win, 3, cur_pos, ACS_VLINE);
  wattroff(win, COLOR_PAIR(Color::BrightWhite));
  wrefresh(win);
}

void ConsoleUI::pauseReplay(bool pause) {
  replay->pause(pause);
  status = pause ? Status::Paused : Status::Playing;
}

void ConsoleUI::handleKey(char c) {
  if (c == '\n') {
    // pause the replay and blocking getchar()
    pauseReplay(true);
    updateStatus();
    curs_set(true);
    nodelay(stdscr, false);

    // Wait for user input
    rWarning("%s", getText(WAITING_INPUT));
    int y = getmaxy(stdscr) - 9;
    move(y, BORDER_SIZE);
    add_str(stdscr, getText(SEEK_REQUEST), Color::BrightWhite, true);
    refresh();

    // Seek to choice
    echo();
    int choice = 0;
    scanw((char *)"%d", &choice);
    noecho();
    pauseReplay(false);
    replay->seekTo(choice, false);

    // Clean up and turn off the blocking mode
    move(y, 0);
    clrtoeol();
    nodelay(stdscr, true);
    curs_set(false);
    refresh();

  } else if (c == 'l' || c == 'L') {
    current_lang = (current_lang == EN) ? ZH : EN;
    // Clear and refresh all windows to show new language
    for (auto win : w) {
      if (win) werase(win);
    }
    initWindows();
  } else if (c == '+' || c == '=') {
    auto it = std::upper_bound(speed_array.begin(), speed_array.end(), replay->getSpeed());
    if (it != speed_array.end()) {
      rWarning("playback speed: %.1fx", *it);
      replay->setSpeed(*it);
    }
  } else if (c == '_' || c == '-') {
    auto it = std::lower_bound(speed_array.begin(), speed_array.end(), replay->getSpeed());
    if (it != speed_array.begin()) {
      auto prev = std::prev(it);
      rWarning("playback speed: %.1fx", *prev);
      replay->setSpeed(*prev);
    }
  } else if (c == 'e') {
    replay->seekToFlag(FindFlag::nextEngagement);
  } else if (c == 'd') {
    replay->seekToFlag(FindFlag::nextDisEngagement);
  } else if (c == 't') {
    replay->seekToFlag(FindFlag::nextUserBookmark);
  } else if (c == 'i') {
    replay->seekToFlag(FindFlag::nextInfo);
  } else if (c == 'w') {
    replay->seekToFlag(FindFlag::nextWarning);
  } else if (c == 'c') {
    replay->seekToFlag(FindFlag::nextCritical);
  } else if (c == 'm') {
    replay->seekTo(+60, true);
  } else if (c == 'M') {
    replay->seekTo(-60, true);
  } else if (c == 's') {
    replay->seekTo(+10, true);
  } else if (c == 'S') {
    replay->seekTo(-10, true);
  } else if (c == ' ') {
    pauseReplay(!replay->isPaused());
  }
}

int ConsoleUI::exec() {
  RateKeeper rk("Replay", 20);

  while (!do_exit) {
    int c = getch();
    if (c == 'q' || c == 'Q') {
      break;
    }
    handleKey(c);

    if (rk.frame() % 25) {
      updateSize();
      updateSummary();
    }

    updateTimeline();
    updateStatus();

    {
      std::scoped_lock lock(mutex);
      updateProgressBar();
      for (auto &[type, msg] : logs) {
        logMessage(type, msg);
      }
      logs.clear();
    }

    rk.keepTime();
  }
  return 0;
}
