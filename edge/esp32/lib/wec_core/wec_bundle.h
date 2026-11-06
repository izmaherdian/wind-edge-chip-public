/* Konstanta mesin WEC untuk ESP32. Dihasilkan otomatis oleh edge/esp32/tools/gen_bundle.py
 * dari dashboard/wec/model_bundle.json (dibuat dashboard/wec/make_bundle.py). Jangan diedit manual. */
#pragma once

/* forecast: p_now, p_lag5, p_lag15, p_lag30, p_lag60, p_mean60, w_now, w_mean10, w_mean60, w3_mean10, dir_sin, dir_cos, hour_sin, hour_cos, rho, om_wind_next */
static const double FC_CENTER[16] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0746736703910906, 0.0};
static const double FC_SCALE[16] = {1.4684844769403536, 1.4634688067837442, 1.4281582071471797, 1.4684844769403536, 1.5117482737734693, 0.9953933069204817, 0.05681102362204724, 0.054770492125984144, 0.05122673950131141, 2.68654040196213, 0.007874015748031496, 0.007874015748031496, 0.007874015748031496, 0.007874015748031496, 0.0003859610454020341, 0.0280807000344219};
static const double FC_W_PER_LSB = 0.9720759041188235;

/* powercurve: w_now, w_mean10, w_mean30, w_mean60, w3_mean10, w3_mean30, w_max10, w_std10, dir_sin, dir_cos, hour_sin, hour_cos, rho, humidity_pct, temp_c, om_wind_now */
static const double PC_CENTER[16] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0745277802860793, 70.7772880727589, 24.613747467472532, 0.0};
static const double PC_SCALE[16] = {0.05724409448818897, 0.056034645669291526, 0.055357217847769154, 0.05554927494922873, 2.838911041377983, 2.751317931240188, 0.06267716535433071, 0.014894829565812662, 0.007874015748031496, 0.007874015748031496, 0.007874015748031496, 0.007874015748031496, 0.00038585708891789895, 0.3680089098305918, 0.10224854524300644, 0.028781889763779548};
static const double PC_W_PER_LSB = 1.350575668426067;

static const double STATUS_BAWAH = 0.4197511587128196;
static const double STATUS_ATAS = 1.4625536061592552;
static const double STATUS_MIN_WAJAR_W = 5.0;

static const double TYP_RHO = 1.0771764954592862;
static const double TYP_TEMP_C = 23.769890741442467;
static const double TYP_RH = 73.5683024691358;

/* interval P10-P90 empiris (kuantil empiris data validasi Agu-Sep) */
#define IV_N 9
static const double IV_DARI[9] = {0.0, 1.0, 2.0, 4.0, 7.0, 12.0, 20.0, 35.0, 60.0};
static const double IV_SAMPAI[9] = {1.0, 2.0, 4.0, 7.0, 12.0, 20.0, 35.0, 60.0, 1000000000.0};
static const double IV_P10[9] = {0.0, 0.57, 0.86, 1.84, 2.94, 4.84, 9.86, 19.99, 41.38};
static const double IV_P90[9] = {4.87, 10.55, 12.34, 14.99, 20.99, 33.19, 51.95, 61.59, 72.25};

/* baterai + inverter (Hoymiles_Converter_Technology__MI_250__240V_) */
static const double BAT_ETA_CHARGE_CONTROLLER = 0.95;
static const double BAT_KAPASITAS_WH = 600.0;
static const double BAT_ETA_ISI = 0.9;
static const double BAT_ETA_BUANG = 0.95;
static const double BAT_SOC_MIN = 0.5;
static const double BAT_SOC_MAX = 1.0;
static const double BAT_SOC_AWAL = 0.75;
static const double BAT_BEBAN_DASAR_W = 6.0;
static const double BAT_BEBAN_MALAM_W = 25.0;
static const int BAT_JAM_MALAM_DARI = 18;
static const int BAT_JAM_MALAM_SAMPAI = 23;
#define INV_N 61
static const double INV_AC_W[61] = {0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0, 30.0, 31.0, 32.0, 33.0, 34.0, 35.0, 36.0, 37.0, 38.0, 39.0, 40.0, 41.0, 42.0, 43.0, 44.0, 45.0, 46.0, 47.0, 48.0, 49.0, 50.0, 51.0, 52.0, 53.0, 54.0, 55.0, 56.0, 57.0, 58.0, 59.0, 60.0};
static const double INV_DC_W[61] = {0.779, 1.843, 2.869, 3.896, 4.923, 5.949, 6.976, 8.003, 9.03, 10.057, 11.084, 12.112, 13.139, 14.166, 15.194, 16.221, 17.249, 18.276, 19.304, 20.331, 21.359, 22.387, 23.415, 24.443, 25.471, 26.499, 27.527, 28.555, 29.584, 30.612, 31.64, 32.669, 33.697, 34.726, 35.755, 36.783, 37.812, 38.841, 39.87, 40.899, 41.928, 42.957, 43.986, 45.015, 46.044, 47.074, 48.103, 49.133, 50.162, 51.192, 52.221, 53.251, 54.281, 55.311, 56.341, 57.371, 58.401, 59.431, 60.461, 61.491, 62.522};
