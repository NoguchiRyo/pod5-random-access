#ifndef POD5_SIGNAL_INDEX_HPP
#define POD5_SIGNAL_INDEX_HPP
#include <cmath>
#pragma once
/**
 * @file    pod5_signal_index.hpp
 * @brief   UUID → signal-table 位置({batch,row}) 逆引きインデックスの
 *          生成・シリアライズ API。
 *
 * 依存ライブラリ
 *   • pod5-format C API（<pod5_format/c_api.h>）
 *   • C++17  〈<array> <vector> <unordered_map> <string>〉
 *
 * 使い方（概要）
 * ------------------------------------------------------------------
 *   pod5_init();
 *   Pod5FileReader_t* rdr = pod5_open_file("run.pod5");
 *
 *   auto idx = pod5::build_signal_index(rdr);
 *   pod5::save_index_bin(idx, "run.sigidx");
 *
 *   auto idx2 = pod5::load_index_bin("run.sigidx");
 *   ...
 *   pod5_close_and_free_reader(rdr);
 *   pod5_terminate();
 * ------------------------------------------------------------------
 */
#include <pod5_format/c_api.h>

#include <array>
#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

namespace pod5 {

/* ------------------------------------------------------------------ */
/*  基本型                                                             */
/* ------------------------------------------------------------------ */

/**
 * @brief 16 byte バイナリ UUID（read_id）そのものをキーにする。
 *        文字列化せず固定幅なのでハッシュも高速 & メモリ節約。
 */
// using ReadId = std::array<std::uint8_t, 16>;

/**
 * @brief ReadId 用のシンプルな FNV-1a ハッシュ。
 *        他アルゴリズムに差し替える場合は operator() だけ入れ替える。
 */
// struct ReadIdHash {
  // std::size_t operator()(ReadId const &id) const noexcept;
// };
using ReadId = std::array<uint8_t, 16>;
struct ReadIdHash {
  size_t operator()(ReadId const &id) const noexcept {
    size_t h = 14695981039346656037ull;
    for (uint8_t b : id) {
      h ^= b;
      h *= 1099511628211ull;
    }
    return h;
  }
};

/**
 * @brief signal テーブル 1 行の所在＋サイズ情報。
 *
 * `stored_sample_count` / `stored_byte_count` は
 * 解析や mmap 読み込み時に役立つ補助情報で、
 * 必要なければ batch / row だけでも運用可能。
 */
struct SigLoc {
  std::uint32_t batch;             //!< signal バッチ index
  std::uint32_t row;               //!< バッチ内 row index
  std::uint32_t n_samples;         //!< 生サンプル数
  std::float_t calibration_offset; //!< キャリブレーションオフセット
  std::float_t calibration_scale;  //!< キャリブレーションスケール
};

/**
 * @brief 逆引きインデックス本体。
 *
 * 1 read が複数 signal 行に分かれるので value は可変長 vector。
 */
using SignalIndex = std::unordered_map<ReadId, std::vector<SigLoc>, ReadIdHash>;

/* ------------------------------------------------------------------ */
/*  インデックスの構築                                                 */
/* ------------------------------------------------------------------ */

/**
 * @brief Open 済み Pod5FileReader からインメモリインデックスを生成。
 *
 * 読み取りは 1 パスで完了。生成に失敗した場合は std::runtime_error。
 *
 * @param reader  pod5_open_file(…) で取得したリーダー
 * @return        構築済み SignalIndex
 */
SignalIndex build_signal_index(Pod5FileReader_t *reader);

/* ------------------------------------------------------------------ */
/*  バイナリシリアライズ                                               */
/* ------------------------------------------------------------------ */

/**
 * @brief インデックスをフラットなバイナリ形式で保存。
 *
 * 連続書き出しなので非常に高速。プラットフォーム差異を避けるため
 * エンディアンを混在させない運用を推奨します。
 *
 * @param index  書き出すインデックス
 * @param path   出力ファイル名
 * @throw        std::runtime_error  I/O エラー時
 */
void save_index_bin(SignalIndex const &index, std::string const &path);

/**
 * @brief save_index_bin() が生成したファイルを読み取り再構築。
 *
 * @param path   入力ファイル名
 * @return       再構築されたインデックス
 * @throw        std::runtime_error  フォーマット不一致・I/O エラー時
 */
SignalIndex load_index_bin(std::string const &path);

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
                                          ReadId const &id);

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
    std::unordered_map<uint32_t, Pod5ReadRecordBatch_t *> &batch_cache);

/**
 * @brief UUID リストを batch ごとに纏め、batch 単位で並列フェッチ
 * @return out_map: 入力の順序に従った各 UUID の信号 vector
 */
std::vector<std::vector<int16_t>> fetch_signals_by_batch(
    Pod5FileReader_t *reader, SignalIndex const &index,
    std::vector<ReadId> const &ids,
    std::unordered_map<uint32_t, Pod5ReadRecordBatch_t *> &batch_cache);
} // namespace pod5
#endif /* POD5_SIGNAL_INDEX_HPP */


