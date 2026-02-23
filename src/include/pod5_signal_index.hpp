#ifndef POD5_SIGNAL_INDEX_HPP
#define POD5_SIGNAL_INDEX_HPP
#pragma once
/**
 * @file    pod5_signal_index.hpp
 * @brief   UUID → Signal Table 位置の逆引きインデックスの
 *          生成・シリアライズ・直接シグナル読み込み API。
 *
 * Runtime では Read Table batch を一切使わず、
 * Signal Table への直接アクセスのみでシグナルを取得する。
 * HDD 上でもシーケンシャルアクセスが可能。
 *
 * 使い方（概要）
 * ------------------------------------------------------------------
 *   pod5_init();
 *   Pod5FileReader_t* rdr = pod5_open_file("run.pod5");
 *
 *   // Build 時のみ Read Table を走査
 *   auto idx = pod5::build_signal_index(rdr);
 *   pod5::save_index_bin(idx, "run.sigidx");
 *
 *   // Runtime: Signal Table 直接アクセス
 *   auto idx2 = pod5::load_index_bin("run.sigidx");
 *   auto sig  = pod5::fetch_signal(rdr, idx2.at(some_id));
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

/// @brief 16 byte バイナリ UUID（read_id）をキーにする。
using ReadId = std::array<uint8_t, 16>;

/// @brief ReadId 用の FNV-1a ハッシュ。
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
 * @brief Signal Table 上のシグナル位置情報。
 *
 * signal_row_start から signal_row_count 個の連続した
 * Signal Table row にシグナルデータが格納されている。
 * Runtime では Read Table batch を経由せず、この情報だけで
 * シグナルを直接読み込める。
 */
struct SigLoc {
  uint64_t signal_row_start;    //!< Signal Table 上の開始 row index
  uint32_t signal_row_count;    //!< 連続する signal row 数
  uint32_t n_samples;           //!< 総サンプル数
  float    calibration_offset;  //!< キャリブレーションオフセット
  float    calibration_scale;   //!< キャリブレーションスケール
};

/// @brief UUID → SigLoc の逆引きインデックス。
using SignalIndex = std::unordered_map<ReadId, SigLoc, ReadIdHash>;

/* ------------------------------------------------------------------ */
/*  インデックスの構築                                                 */
/* ------------------------------------------------------------------ */

/**
 * @brief Open 済み Pod5FileReader からインメモリインデックスを生成。
 *
 * Read Table の全バッチを 1 パスで走査し、各リードの
 * signal row indices・サンプル数・キャリブレーション情報を抽出する。
 * バッチは走査後に即解放され、メモリには SigLoc のみ残る。
 *
 * @param reader  pod5_open_file() で取得したリーダー
 * @return        構築済み SignalIndex
 * @throw         std::runtime_error  pod5 API エラー時
 */
SignalIndex build_signal_index(Pod5FileReader_t *reader);

/* ------------------------------------------------------------------ */
/*  バイナリシリアライズ                                               */
/* ------------------------------------------------------------------ */

/**
 * @brief インデックスをフラットなバイナリ形式で保存。
 *
 * 各エントリは固定長 (ReadId 16B + SigLoc 24B = 40B) で、
 * 連続書き出しにより高速にシリアライズされる。
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

/* ------------------------------------------------------------------ */
/*  シグナル読み込み（Signal Table 直接アクセス）                      */
/* ------------------------------------------------------------------ */

/**
 * @brief SigLoc を使って Signal Table からシグナルを直接読み込む。
 *
 * Read Table batch を経由せず、pod5_get_signal_row_info +
 * pod5_get_signal で Signal Table に直接アクセスする。
 * HDD 上でも Read Table 領域へのシークが発生しない。
 *
 * @param reader  open 済みの Pod5FileReader
 * @param loc     インデックスから取得した SigLoc
 * @return        シグナルデータ（int16 サンプル列）
 * @throw         std::runtime_error  pod5 API エラー時
 */
std::vector<int16_t> fetch_signal(Pod5FileReader_t *reader, SigLoc const &loc);

/**
 * @brief SigLoc を使って pA キャリブレーション済みシグナルを取得する。
 *
 * 内部で fetch_signal() を呼び、SigLoc 内の calibration 情報で
 * (raw + offset) * scale の変換を行う。
 * hashmap lookup は呼び出し側で 1 回だけ行えばよい。
 *
 * @param reader  open 済みの Pod5FileReader
 * @param loc     インデックスから取得した SigLoc
 * @return        pA 変換済みシグナルデータ（float）
 * @throw         std::runtime_error  pod5 API エラー時
 */
std::vector<float> fetch_pA_signal(Pod5FileReader_t *reader, SigLoc const &loc);

/* ------------------------------------------------------------------ */
/*  ソート（HDD シーケンシャルアクセス最適化）                         */
/* ------------------------------------------------------------------ */

/**
 * @brief UUID リストを Signal Table 上の物理位置順にソートする。
 *
 * signal_row_start 昇順にソートすることで、HDD 上で
 * Signal Table を先頭から順にアクセスするパターンになる。
 *
 * @param index  構築済みインデックス
 * @param ids    ソート対象の UUID リスト
 * @return       ソート後の元インデックス配列（ids への添字）
 * @throw        std::out_of_range  UUID がインデックスに存在しない場合
 */
std::vector<size_t> sort_by_location(SignalIndex const &index,
                                     std::vector<ReadId> const &ids);

} // namespace pod5
#endif /* POD5_SIGNAL_INDEX_HPP */
