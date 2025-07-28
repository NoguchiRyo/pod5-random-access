#include "pod5_signal_index.hpp"
#include "pod5_format/c_api.h"

#include <array>
#include <cstdint> // 追加
#include <cstring>
#include <fstream> // 追加
#include <future>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string> // 追加
#include <unordered_map>
#include <vector>

namespace pod5 {
// 16-byte UUID をキーにする -------------------------------------------------
// using ReadId = std::array<uint8_t, 16>;
// struct ReadIdHash {
//   size_t operator()(ReadId const &id) const noexcept {
//     size_t h = 14695981039346656037ull;
//     for (uint8_t b : id) {
//       h ^= b;
//       h *= 1099511628211ull;
//     }
//     return h;
//   }
// };

// signal 側 1 行分の場所＋サイズ -------------------------------------------
// struct SigLoc {
//   uint32_t batch;     // batch index
//   uint32_t row;       // row index
//   uint32_t n_samples; // このリードのサンプル数
//   // uint32_t n_bytes;   // 圧縮後サイズ（今は未使用なら 0）
//   float calibration_offset;
//   float callibration_scale;
// };
static_assert(sizeof(SigLoc) == 20, "SigLoc must be 16 bytes");

using SignalIndex = std::unordered_map<ReadId, std::vector<SigLoc>, ReadIdHash>;

// --------------------------------------------------------------------------
SignalIndex build_signal_index(Pod5FileReader_t *reader) {
  SignalIndex idx;

  // std::cerr << "[C++] build_signal_index() start" << std::endl;

  // (A) read バッチ数を取得
  size_t batch_count = 0;
  if (pod5_get_read_batch_count(&batch_count, reader) != POD5_OK) {
    throw std::runtime_error("pod5_get_read_batch_count failed");
  }
  // std::cerr << "[C++] batch_count = " << batch_count << std::endl;

  // (B) 各バッチを順に処理
  for (size_t b = 0; b < batch_count; ++b) {
    // std::cerr << "[C++] processing batch " << b << "/" << batch_count
    //           << std::endl;

    // バッチ取得
    Pod5ReadRecordBatch_t *batch = nullptr;
    if (pod5_get_read_batch(&batch, reader, b) != POD5_OK) {
      throw std::runtime_error("pod5_get_read_batch failed");
    }

    // バッチ内の行数
    size_t row_count = 0;
    if (pod5_get_read_batch_row_count(&row_count, batch) != POD5_OK) {
      pod5_free_read_batch(batch);
      throw std::runtime_error("pod5_get_read_batch_row_count failed");
    }
    // std::cerr << "[C++] row_count = " << row_count << std::endl;

    // 各行（=１リード）ごとに UUID → SigLoc を登録
    for (size_t r = 0; r < row_count; ++r) {
      // (1) read_row_info から UUID を取得
      ReadBatchRowInfo_t info{};
      uint16_t table_ver = 0;
      if (pod5_get_read_batch_row_info_data(batch, r,
                                            READ_BATCH_ROW_INFO_VERSION, &info,
                                            &table_ver) != POD5_OK) {
        pod5_free_read_batch(batch);
        throw std::runtime_error("pod5_get_read_batch_row_info_data failed");
      }

      // (2) この read の生サンプル総数を取得
      size_t sample_count = 0;
      if (pod5_get_read_complete_sample_count(reader, batch, r,
                                              &sample_count) != POD5_OK) {
        pod5_free_read_batch(batch);
        throw std::runtime_error("pod5_get_read_complete_sample_count failed");
      }

      // デバッグログ
      // if (r == 0) {
      //   std::cerr << "[C++] b=" << b << " r=" << r
      //             << " samples=" << sample_count << std::endl;
      // }
      // (3) map へ追加
      ReadId id;
      std::memcpy(id.data(), info.read_id, 16);

      SigLoc loc{
          static_cast<uint32_t>(b),
          static_cast<uint32_t>(r),
          static_cast<uint32_t>(sample_count),
          static_cast<float>(info.calibration_offset),
          static_cast<float>(info.calibration_scale),
      };

      // if (r == 0) {
      //   std::cerr << "[C++] batch=" << loc.batch << " row=" << loc.row
      //             << " n_samples=" << loc.n_samples
      //             << " calibration_offset=" << loc.calibration_offset
      //             << " calibration_scale=" << loc.callibration_scale
      //             << std::endl;
      // }

      idx[id].push_back(loc);
    }

    // check the first entry
    // if (b == 0 && row_count > 0) {
    //   auto it = idx.find(idx.begin()->first);
    //   if (it != idx.end()) {
    //     const auto &locs = it->second;
    //     std::cerr << "[C++] First entry: batch=" << locs.front().batch
    //               << " row=" << locs.front().row
    //               << " n_samples=" << locs.front().n_samples
    //               << " calibration_offset=" <<
    //               locs.front().calibration_offset
    //               << " calibration_scale=" << locs.front().callibration_scale
    //               << std::endl;
    //   }
    // }

    // 解放
    if (pod5_free_read_batch(batch) != POD5_OK) {
      throw std::runtime_error("pod5_free_read_batch failed");
    }
  }

  // std::cerr << "[C++] build_signal_index() done" << std::endl;
  return idx;
}

static constexpr char MAGIC[6] = "P5IDX";
static constexpr uint16_t VERSION = 0;

struct FileHeader {
  char magic[6];
  uint16_t ver;
  uint16_t reserved{};
  uint64_t entry_count{};
};

struct SigLocPacked {
  uint32_t batch;
  uint32_t row;
  uint32_t n_samples;
  float calibration_offset;
  float calibration_scale;
};

void save_index_bin(const SignalIndex &idx, const std::string &path) {
  std::ofstream ofs(path, std::ios::out | std::ios::trunc | std::ios::binary);
  if (!ofs)
    throw std::runtime_error("open failed");

  // --- ヘッダー ----------------------------------------------------------
  FileHeader hdr{};
  std::memcpy(hdr.magic, MAGIC, 6);
  hdr.ver = VERSION;
  hdr.entry_count = idx.size();
  ofs.write(reinterpret_cast<char *>(&hdr), sizeof hdr);

  // --- 本体 -------------------------------------------------------------
  // std::cerr << "[C++] writing index, entry_count=" << idx.size() <<
  // std::endl;
  for (auto const &[key, vec] : idx) {

    // std::cerr << "[C++] writing\n";
    // std::cerr << "Key Size: " << key.size() << "\n";
    // std::cerr << "Value Size: " << vec.size() << "\n";
    // key (16 byte)
    ofs.write(reinterpret_cast<char const *>(key.data()), key.size());

    // チャンク数
    uint32_t m = static_cast<uint32_t>(vec.size());
    ofs.write(reinterpret_cast<char *>(&m), sizeof m);

    // value array
    for (auto const &v : vec) {
      // std::cerr << "[C++] writing SigLoc\n";
      // std::cerr << "batch: " << v.batch << "\n";
      // std::cerr << "row: " << v.row << "\n";
      // std::cerr << "n_samples: " << v.n_samples << "\n";

      ofs.write(reinterpret_cast<const char *>(&v), sizeof v);
    }
  }
}

SignalIndex load_index_bin(const std::string &path) {
  std::ifstream ifs(path, std::ios::binary);
  if (!ifs)
    throw std::runtime_error("open failed");

  // --- ヘッダー確認 ------------------------------------------------------
  FileHeader hdr{};
  ifs.read(reinterpret_cast<char *>(&hdr), sizeof hdr);
  if (std::memcmp(hdr.magic, MAGIC, 6) || hdr.ver != VERSION)
    throw std::runtime_error("format mismatch");

  SignalIndex idx;
  idx.reserve(static_cast<size_t>(hdr.entry_count * 1.3));

  // --- 本体 -------------------------------------------------------------
  for (uint64_t i = 0; i < hdr.entry_count; ++i) {

    ReadId key{};
    ifs.read(reinterpret_cast<char *>(key.data()), key.size());

    uint32_t m = 0;
    ifs.read(reinterpret_cast<char *>(&m), sizeof m);

    std::vector<SigLoc> vec;
    vec.reserve(m);

    for (uint32_t j = 0; j < m; ++j) {
      SigLocPacked p;
      ifs.read(reinterpret_cast<char *>(&p), sizeof p);
      vec.push_back({p.batch, p.row, p.n_samples, p.calibration_offset,
                     p.calibration_scale});
    }
    idx.emplace(std::move(key), std::move(vec));
  }
  return idx;
}

// -----------------------------------------------------------------------------
//  UUID → vector<int16_t> 取得
// -----------------------------------------------------------------------------
/**
 * @brief  read_id(UUID) で指定されたリードの生信号を取得する。
 *
 * @param reader  既に open 済みの Pod5FileReader
 * @param index   build_signal_index() で得たインデックス
 * @param id      16-byte バイナリ UUID（ReadId）
 * @return        その read の signal（サンプル単位）
 *
 * @throw std::out_of_range   UUID が index に存在しない
 * @throw std::runtime_error  pod5 API エラー
 */
std::vector<int16_t> fetch_signal_by_uuid(Pod5FileReader_t *reader,
                                          SignalIndex const &index,
                                          ReadId const &id) {
  // 1) UUID で SigLoc を探す
  auto it = index.find(id);
  if (it == index.end()) {
    throw std::out_of_range("UUID not found in SignalIndex");
  }
  auto const &locs = it->second;
  if (locs.empty()) {
    throw std::runtime_error("No SigLoc entries for this UUID");
  }

  // SigLoc は１件目（通常は唯一）のみを使う
  const SigLoc &loc = locs.front();

  // 2) 全サンプル数を取得
  size_t sample_count = loc.n_samples;
  std::vector<int16_t> signal(sample_count);

  // 3) バッチを開いて一発でデータを取る
  Pod5ReadRecordBatch_t *batch = nullptr;
  if (pod5_get_read_batch(&batch, reader, loc.batch) != POD5_OK) {
    throw std::runtime_error("pod5_get_read_batch failed");
  }

  if (pod5_get_read_complete_signal(reader, batch, loc.row, sample_count,
                                    signal.data()) != POD5_OK) {
    pod5_free_read_batch(batch);
    throw std::runtime_error("pod5_get_read_complete_signal failed");
  }

  pod5_free_read_batch(batch);
  return signal;
}

/**
 * @brief  UUID → signal を取得しつつ、バッチをキャッシュして使い回します。
 * @param  reader      open 済みの Pod5FileReader
 * @param  index       build_signal_index() で得たインデックス
 * @param  id          16-byte バイナリ UUID（ReadId）
 * @param  batch_cache バッチインデックス→Pod5ReadRecordBatch* のキャッシュ
 * @return             その read の signal（サンプル単位）
 * @throw std::out_of_range   UUID が index に存在しない
 * @throw std::runtime_error  pod5 API エラー
 */

std::vector<int16_t> fetch_signal_by_uuid_and_batch(
    Pod5FileReader_t *reader, SignalIndex const &index, ReadId const &id,
    std::unordered_map<uint32_t, Pod5ReadRecordBatch_t *> &batch_cache) {
  auto it = index.find(id);
  if (it == index.end())
    throw std::out_of_range("UUID not found in SignalIndex");
  const SigLoc &loc = it->second.front();

  Pod5ReadRecordBatch_t *batch = nullptr;
  auto cache_it = batch_cache.find(loc.batch);
  if (cache_it == batch_cache.end()) {
    if (pod5_get_read_batch(&batch, reader, loc.batch) != POD5_OK)
      throw std::runtime_error("pod5_get_read_batch failed");
    batch_cache[loc.batch] = batch;
  } else {
    batch = cache_it->second;
  }

  size_t n = loc.n_samples;
  std::vector<int16_t> signal(n);
  if (pod5_get_read_complete_signal(reader, batch, loc.row, n, signal.data()) !=
      POD5_OK)
    throw std::runtime_error("pod5_get_read_complete_signal failed");
  return signal;
}

/**
 * @brief UUID リストを batch ごとに纏め、batch 単位で並列フェッチ
 * @return out_map: 入力の順序に従った各 UUID の信号 vector
 */
std::vector<std::vector<int16_t>> fetch_signals_by_batch(
    Pod5FileReader_t *reader, SignalIndex const &index,
    std::vector<ReadId> const &ids,
    std::unordered_map<uint32_t, Pod5ReadRecordBatch_t *> &batch_cache) {
  // (1) UUID→SigLoc、batch→一覧インデックスを作成
  std::map<uint32_t, std::vector<size_t>> batch_to_positions;
  std::vector<const SigLoc *> locs(ids.size());
  for (size_t i = 0; i < ids.size(); ++i) {
    auto it = index.find(ids[i]);
    if (it == index.end())
      throw std::out_of_range("UUID not in index");
    const SigLoc &loc = it->second.front();
    locs[i] = &loc;
    batch_to_positions[loc.batch].push_back(i);
  }

  // 出力コンテナ
  std::vector<std::vector<int16_t>> out(ids.size());

  // (2) batch ごとに async 実行
  std::vector<std::future<void>> futures;
  for (auto &kv : batch_to_positions) {
    uint32_t batch_id = kv.first;
    auto &positions = kv.second;
    futures.emplace_back(
        std::async(std::launch::async, [&, batch_id, positions]() {
          // バッチ取得
          Pod5ReadRecordBatch_t *batch = nullptr;
          auto itc = batch_cache.find(batch_id);
          if (itc == batch_cache.end()) {
            if (pod5_get_read_batch(&batch, reader, batch_id) != POD5_OK)
              throw std::runtime_error("pod5_get_read_batch failed");
            batch_cache[batch_id] = batch;
          } else {
            batch = itc->second;
          }
          // 各 pos について信号取得
          for (auto pos : positions) {
            auto const &loc = *locs[pos];
            size_t n = loc.n_samples;
            out[pos].resize(n);
            if (pod5_get_read_complete_signal(reader, batch, loc.row, n,
                                              out[pos].data()) != POD5_OK) {
              throw std::runtime_error("pod5_get_read_complete_signal failed");
            }
          }
        }));
  }
  // 全タスク完了待ち
  for (auto &f : futures)
    f.get();
  return out;
}

} // namespace pod5
