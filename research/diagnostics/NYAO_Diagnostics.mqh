// Nyao diagnostic sidecar: Strategy Tester ONLY. Does not send orders or modify entry/exit decisions.
// Records closed-position snapshots with observed bid/ask tick MFE/MAE. Experimental, not a profit claim.
struct DxSnapshot
{
   double score;
   double threshold;
   double efficiency;
   double atr;
   double spreadPoints;
   double trendRange;
   double trendEma;
   double trendEfficiency;
   double trendMomentum;
   double penalty;
   double drawdownPct;
   datetime signalBar;
};

struct DxTrade
{
   ulong ticket;
   int direction;
   datetime opened;
   double volume;
   double entry;
   double initialSl;
   double initialTp;
   double lastObservedSl;
   DxSnapshot snapshot;
   double mfePrice;
   double maePrice;
   double maxSpreadPoints;
   long observedTicks;
};


// One watch per genuinely loss-making, broker-SL-closed position.
// Follow subsequent tester ticks without opening/changing a single order.
struct DxPostStop
{
   ulong ticket;
   int direction;
   datetime entryTime;
   double entryPrice;
   double exitPrice;
   double net;
   double checkpointDistance;
   long exitMs;
   long firstTickMs;
   long lastTickMs;
   long firstReturnMs;
   long firstPlus5Ms;
   long firstCheckpointMs;
   long observedTicks;
   double maxAdverseBeforeReturn;
   double maxAdditionalAdverse;
   double maxFavorable;
};

int _dxPostHandle = INVALID_HANDLE;
string _dxPostPath = "NYAO_STOP_RECOVERY_TICKS.csv";
DxPostStop _dxPostActive[];

int _dxHandle = INVALID_HANDLE;
DxTrade _dxActive[];
string _dxPath = "NYAO_ENTRY_DIAGNOSTICS.csv";
bool _dxWriteFailed = false;

bool DxInit()
{
   if(!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))
      return false;
   ArrayResize(_dxActive, 0);
   ArrayResize(_dxPostActive, 0);
   _dxPostHandle = INVALID_HANDLE;
   _dxWriteFailed = false;
   // Do not silently overwrite a previous test's evidence.
   if(FileIsExist(_dxPath, FILE_COMMON) || FileIsExist(_dxPostPath, FILE_COMMON))
   {
      Print("[DX] STOP: existing evidence CSV. Archive both ", _dxPath, " and ",
            _dxPostPath, " before re-testing; nothing will be overwritten.");
      return false;
   }
   ResetLastError();
   _dxHandle = FileOpen(_dxPath, FILE_COMMON | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ, ',');
   if(_dxHandle == INVALID_HANDLE)
   {
      PrintFormat("[DX] Cannot open tester CSV, error %d. No backtest will run.", GetLastError());
      return false;
   }
   uint wrote = FileWrite(_dxHandle,
      "schema", "ticket", "symbol", "period", "direction", "entry_time", "entry_price",
      "volume", "entry_spread_points", "score", "threshold", "efficiency_20",
      "atr_closed", "trend_range", "trend_ema", "trend_efficiency", "trend_momentum",
      "losing_penalty", "drawdown_pct", "signal_bar", "initial_sl", "initial_tp",
      "exit_time", "exit_price", "exit_reason_code", "exit_comment", "net_profit_usd",
      "mfe_price", "mae_price", "mfe_points", "mae_points", "observed_ticks",
      "max_spread_points", "last_observed_sl", "adverse_sl_gap_price", "status");
   if(wrote == 0)
   {
      PrintFormat("[DX] Cannot write CSV header, error %d.", GetLastError());
      FileClose(_dxHandle); _dxHandle = INVALID_HANDLE;
      return false;
   }
   ResetLastError();
   _dxPostHandle = FileOpen(_dxPostPath, FILE_COMMON | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ, ',');
   if(_dxPostHandle == INVALID_HANDLE)
   {
      PrintFormat("[DX] Cannot open post-stop tick CSV, error %d. Test blocked.", GetLastError());
      FileClose(_dxHandle); _dxHandle = INVALID_HANDLE;
      FileDelete(_dxPath, FILE_COMMON); // only the file newly created during this init
      return false;
   }
   uint stopHeader = FileWrite(_dxPostHandle,
      "schema", "ticket", "symbol", "period", "direction",
      "entry_time", "entry_price", "exit_price", "net_usd",
      "checkpoint_distance_price", "exit_time_ms", "window_end_ms",
      "first_observed_tick_ms", "last_observed_tick_ms", "observed_ticks",
      "first_return_to_entry_ms", "first_plus5_ms", "first_checkpoint_ms",
      "max_adverse_before_return_price", "max_additional_adverse_after_exit_price",
      "max_favorable_after_exit_price", "status");
   if(stopHeader == 0)
   {
      PrintFormat("[DX] Cannot write post-stop header, error %d. Test blocked.", GetLastError());
      FileClose(_dxPostHandle); _dxPostHandle = INVALID_HANDLE;
      FileClose(_dxHandle); _dxHandle = INVALID_HANDLE;
      FileDelete(_dxPostPath, FILE_COMMON);
      FileDelete(_dxPath, FILE_COMMON);
      return false;
   }
   FileFlush(_dxPostHandle);
   FileFlush(_dxHandle);
   Print("[DX] Research CSV: MetaQuotes\\Terminal\\Common\\Files\\", _dxPath,
         ". No real/live trading permitted with this diagnostic variant.");
   return true;
}

void DxSnapshotBeforeSend(ENUM_ORDER_TYPE side, double score, double bid, double ask, DxSnapshot &snap)
{
   bool isBuy = (side == ORDER_TYPE_BUY);
   snap.score = score;
   EntryScore e;
   ComputeEntryScore(isBuy, e); // read-only, same closed-bar cached scoring as the approved signal
   snap.threshold = e.threshold;
   snap.penalty = e.penalty;
   snap.drawdownPct = e.ddPct;
   snap.trendRange = e.strength.trendRange;
   snap.trendEma = e.strength.trendEma;
   snap.trendEfficiency = e.strength.trendEfficiency;
   snap.trendMomentum = e.strength.trendMomentum;
   snap.efficiency = DirectionalEfficiency(isBuy, RangeFilterPeriod);
   snap.signalBar = iTime(_Symbol, _Period, 1);
   snap.spreadPoints = (_Point > 0) ? (ask - bid) / _Point : 0;
   snap.atr = 0;
   double atrBuffer[];
   if(atrSignalHandle != INVALID_HANDLE &&
      CopyBuffer(atrSignalHandle, 0, 1, 1, atrBuffer) == 1)
      snap.atr = atrBuffer[0];
}

void DxObserve(DxTrade &trade, double bid, double ask)
{
   if(bid <= 0 || ask <= 0 || ask < bid) return;
   double liquidation = (trade.direction == 1) ? bid : ask;
   double signedMove = (trade.direction == 1) ? (liquidation - trade.entry)
                                                 : (trade.entry - liquidation);
   if(signedMove > trade.mfePrice) trade.mfePrice = signedMove;
   if(-signedMove > trade.maePrice) trade.maePrice = -signedMove;
   if(_Point > 0)
   {
      double spread = (ask - bid) / _Point;
      if(spread > trade.maxSpreadPoints) trade.maxSpreadPoints = spread;
   }
   trade.observedTicks++;
}

void DxTrackFilledPosition(ulong positionTicket, ENUM_ORDER_TYPE side, double fallbackEntry,
                           double volume, double sl, double tp, DxSnapshot &snapshot)
{
   if(_dxHandle == INVALID_HANDLE || positionTicket == 0) return;
   for(int i=0; i<ArraySize(_dxActive); i++)
      if(_dxActive[i].ticket == positionTicket) return;
   int n = ArraySize(_dxActive);
   if(n >= 64)
   {
      Print("[DX] FAIL: max tracked positions exceeded; evidence incomplete.");
      _dxWriteFailed = true;
      return;
   }
   DxTrade t;
   t.ticket = positionTicket;
   t.direction = side == ORDER_TYPE_BUY ? 1 : -1;
   t.opened = TimeCurrent();
   t.volume = volume;
   t.entry = fallbackEntry;
   t.initialSl = sl;
   t.initialTp = tp;
   t.lastObservedSl = sl;
   t.snapshot = snapshot;
   t.mfePrice = 0;
   t.maePrice = 0;
   t.maxSpreadPoints = snapshot.spreadPoints;
   t.observedTicks = 0;
   if(PositionSelectByTicket(positionTicket))
   {
      t.entry = PositionGetDouble(POSITION_PRICE_OPEN);
      t.opened = (datetime)PositionGetInteger(POSITION_TIME);
      t.volume = PositionGetDouble(POSITION_VOLUME);
   }
   ArrayResize(_dxActive, n+1);
   _dxActive[n] = t;
}

// Exact tester tick record: executable BID for closed BUYs and ASK for closed SELLs.
// All timestamps are broker-server milliseconds. A missing hit is not a future tick prediction.
void DxWritePostStop(DxPostStop &w, string status)
{
   if(_dxPostHandle == INVALID_HANDLE) { _dxWriteFailed = true; return; }
   uint wrote = FileWrite(_dxPostHandle,
      "1", (string)w.ticket, _Symbol, EnumToString(_Period),
      w.direction == 1 ? "BUY" : "SELL",
      TimeToString(w.entryTime, TIME_DATE | TIME_SECONDS),
      DoubleToString(w.entryPrice, _Digits), DoubleToString(w.exitPrice, _Digits),
      DoubleToString(w.net, 2), DoubleToString(w.checkpointDistance, _Digits),
      (string)w.exitMs, (string)(w.exitMs + 86400000),
      w.firstTickMs > 0 ? (string)w.firstTickMs : "",
      w.lastTickMs > 0 ? (string)w.lastTickMs : "",
      (string)w.observedTicks,
      w.firstReturnMs > 0 ? (string)w.firstReturnMs : "",
      w.firstPlus5Ms > 0 ? (string)w.firstPlus5Ms : "",
      w.firstCheckpointMs > 0 ? (string)w.firstCheckpointMs : "",
      DoubleToString(w.maxAdverseBeforeReturn, _Digits),
      DoubleToString(w.maxAdditionalAdverse, _Digits),
      DoubleToString(w.maxFavorable, _Digits), status);
   if(wrote == 0)
   {
      _dxWriteFailed = true;
      PrintFormat("[DX] Post-stop row failed: ticket %I64u, error %d.", w.ticket, GetLastError());
   }
   FileFlush(_dxPostHandle);
}

void DxObservePostStops(MqlTick &tick)
{
   if(_dxPostHandle == INVALID_HANDLE || ArraySize(_dxPostActive) == 0) return;
   if(tick.bid <= 0 || tick.ask <= 0 || tick.ask < tick.bid) return;
   long ms = (tick.time_msc > 0) ? tick.time_msc : (long)tick.time * 1000;
   for(int i=ArraySize(_dxPostActive)-1; i>=0; i--)
   {
      DxPostStop w = _dxPostActive[i];
      if(ms <= w.exitMs) continue; // never use the stop-filling tick itself as a rebound
      if(ms > w.exitMs + 86400000)
      {
         DxWritePostStop(w, w.observedTicks > 0 ? "WINDOW_ELAPSED" : "NO_TICKS_IN_WINDOW");
         _dxPostActive[i] = _dxPostActive[ArraySize(_dxPostActive)-1];
         ArrayResize(_dxPostActive, ArraySize(_dxPostActive)-1);
         continue;
      }
      double px = w.direction == 1 ? tick.bid : tick.ask;
      double move = w.direction * (px - w.entryPrice);
      double extraAdverse = -w.direction * (px - w.exitPrice);
      if(w.firstTickMs == 0) w.firstTickMs = ms;
      w.lastTickMs = ms;
      w.observedTicks++;
      if(move > w.maxFavorable) w.maxFavorable = move;
      if(extraAdverse > w.maxAdditionalAdverse) w.maxAdditionalAdverse = extraAdverse;
      if(w.firstReturnMs == 0 && -move > w.maxAdverseBeforeReturn)
         w.maxAdverseBeforeReturn = -move;
      if(w.firstReturnMs == 0 && move >= 0.0) w.firstReturnMs = ms;
      if(w.firstPlus5Ms == 0 && move >= 5.0) w.firstPlus5Ms = ms;
      if(w.checkpointDistance > 0 && w.firstCheckpointMs == 0 &&
         move >= w.checkpointDistance)
         w.firstCheckpointMs = ms;
      _dxPostActive[i] = w;
   }
}

void DxRegisterPostStop(DxTrade &trade, ulong exitDeal, double totalNet)
{
   if(_dxPostHandle == INVALID_HANDLE || totalNet >= -0.005 ||
      HistoryDealGetInteger(exitDeal, DEAL_REASON) != DEAL_REASON_SL)
      return;
   if(ArraySize(_dxPostActive) >= 256)
   {
      _dxWriteFailed = true;
      Print("[DX] STOP-RECOVERY: 256 concurrent watches exceeded; evidence incomplete.");
      return;
   }
   DxPostStop w;
   w.ticket = trade.ticket;
   w.direction = trade.direction;
   w.entryTime = trade.opened;
   w.entryPrice = trade.entry;
   w.exitPrice = HistoryDealGetDouble(exitDeal, DEAL_PRICE);
   w.net = totalNet;
   w.exitMs = (long)HistoryDealGetInteger(exitDeal, DEAL_TIME_MSC);
   if(w.exitMs <= 0) w.exitMs = (long)HistoryDealGetInteger(exitDeal, DEAL_TIME) * 1000;
   w.checkpointDistance = GetTPPoints(trade.volume) * _Point;
   w.firstTickMs = 0;
   w.lastTickMs = 0;
   w.firstReturnMs = 0;
   w.firstPlus5Ms = 0;
   w.firstCheckpointMs = 0;
   w.observedTicks = 0;
   w.maxAdverseBeforeReturn = MathMax(0.0, -w.direction * (w.exitPrice - w.entryPrice));
   w.maxAdditionalAdverse = 0;
   w.maxFavorable = 0;
   if(w.exitMs <= 0 || w.checkpointDistance <= 0)
   {
      _dxWriteFailed = true;
      PrintFormat("[DX] STOP-RECOVERY missing clock/target for position %I64u.", trade.ticket);
      return;
   }
   int n = ArraySize(_dxPostActive);
   ArrayResize(_dxPostActive, n+1);
   _dxPostActive[n] = w;
}

void DxOnTick()
{
   if(_dxHandle == INVALID_HANDLE) return;
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;
   DxObservePostStops(tick); // observes even when no trading position is open
   for(int i=0; i<ArraySize(_dxActive); i++)
   {
      if(!PositionSelectByTicket(_dxActive[i].ticket)) continue;
      DxObserve(_dxActive[i], tick.bid, tick.ask);
      _dxActive[i].lastObservedSl = PositionGetDouble(POSITION_SL);
   }
}

void DxWriteRow(DxTrade &t, string closeTime, string closePrice, string reason, string comment,
                string net, string slGap, string status)
{
   if(_dxHandle == INVALID_HANDLE) return;
   uint written = FileWrite(_dxHandle,
      "1", (string)t.ticket, _Symbol, EnumToString(_Period),
      t.direction == 1 ? "BUY" : "SELL",
      TimeToString(t.opened, TIME_DATE | TIME_SECONDS),
      DoubleToString(t.entry, _Digits),
      DoubleToString(t.volume, 2),
      DoubleToString(t.snapshot.spreadPoints, 2),
      DoubleToString(t.snapshot.score, 4),
      DoubleToString(t.snapshot.threshold, 4),
      DoubleToString(t.snapshot.efficiency, 5),
      DoubleToString(t.snapshot.atr, _Digits),
      DoubleToString(t.snapshot.trendRange, 5),
      DoubleToString(t.snapshot.trendEma, 5),
      DoubleToString(t.snapshot.trendEfficiency, 5),
      DoubleToString(t.snapshot.trendMomentum, 5),
      DoubleToString(t.snapshot.penalty, 4),
      DoubleToString(t.snapshot.drawdownPct, 4),
      TimeToString(t.snapshot.signalBar, TIME_DATE | TIME_SECONDS),
      DoubleToString(t.initialSl, _Digits),
      DoubleToString(t.initialTp, _Digits),
      closeTime, closePrice, reason, comment, net,
      DoubleToString(t.mfePrice, _Digits),
      DoubleToString(t.maePrice, _Digits),
      DoubleToString(_Point > 0 ? t.mfePrice/_Point : 0, 1),
      DoubleToString(_Point > 0 ? t.maePrice/_Point : 0, 1),
      (string)t.observedTicks,
      DoubleToString(t.maxSpreadPoints, 2),
      DoubleToString(t.lastObservedSl, _Digits),
      slGap, status);
   if(written == 0)
   {
      _dxWriteFailed = true;
      PrintFormat("[DX] CSV write failed for position %I64u, error %d.", t.ticket, GetLastError());
   }
   FileFlush(_dxHandle); // survives intermittent test aborts without altering trading logic
}

void DxOnClosedPosition(ulong positionTicket, double totalNet)
{
   if(_dxHandle == INVALID_HANDLE) return;
   int index = -1;
   for(int i=0; i<ArraySize(_dxActive); i++)
      if(_dxActive[i].ticket == positionTicket) { index = i; break; }
   if(index == -1)
   {
      _dxWriteFailed = true;
      PrintFormat("[DX] Closed position %I64u has no tracked entry; incomplete evidence.", positionTicket);
      return;
   }
   DxTrade trade = _dxActive[index];
   string closeTime = "", closePrice = "", reason = "", comment = "", slGap = "";
   bool haveExit = false;
   double exitPrice = 0;
   if(HistorySelectByPosition(positionTicket))
   {
      datetime lastTime = 0;
      ulong lastDeal = 0;
      for(int d=0; d<HistoryDealsTotal(); d++)
      {
         ulong deal = HistoryDealGetTicket(d);
         if(deal == 0) continue;
         long entry = HistoryDealGetInteger(deal, DEAL_ENTRY);
         if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY && entry != DEAL_ENTRY_INOUT)
            continue;
         datetime when = (datetime)HistoryDealGetInteger(deal, DEAL_TIME);
         if(lastDeal == 0 || when > lastTime || (when == lastTime && deal > lastDeal))
         {
            lastTime = when;
            lastDeal = deal;
         }
      }
      if(lastDeal > 0)
      {
         haveExit = true;
         exitPrice = HistoryDealGetDouble(lastDeal, DEAL_PRICE);
         closeTime = TimeToString(lastTime, TIME_DATE | TIME_SECONDS);
         closePrice = DoubleToString(exitPrice, _Digits);
         reason = IntegerToString((int)HistoryDealGetInteger(lastDeal, DEAL_REASON));
         comment = HistoryDealGetString(lastDeal, DEAL_COMMENT);
         double signedMove = trade.direction == 1 ? exitPrice - trade.entry
                                                   : trade.entry - exitPrice;
         if(signedMove > trade.mfePrice) trade.mfePrice = signedMove;
         if(-signedMove > trade.maePrice) trade.maePrice = -signedMove;
         // This is only an estimate relative to the LAST OBSERVED stop, not a claim
         // about the actual stop level that triggered the closing deal.
         if(trade.lastObservedSl > 0)
         {
            double adverse = trade.direction == 1 ? trade.lastObservedSl - exitPrice
                                                   : exitPrice - trade.lastObservedSl;
            slGap = DoubleToString(MathMax(0.0, adverse), _Digits);
         }
         DxRegisterPostStop(trade, lastDeal, totalNet); // SL-loss only, no order changes
      }
   }
   DxWriteRow(trade, closeTime, closePrice, reason, comment, DoubleToString(totalNet, 2),
              slGap, haveExit ? "CLOSED" : "EXIT_DEAL_NOT_FOUND");
   for(int j=index; j<ArraySize(_dxActive)-1; j++) _dxActive[j] = _dxActive[j+1];
   ArrayResize(_dxActive, ArraySize(_dxActive)-1);
}

void DxFinish()
{
   if(_dxHandle == INVALID_HANDLE) return;
   for(int i=0; i<ArraySize(_dxActive); i++)
      DxWriteRow(_dxActive[i], "", "", "", "", "", "", "OPEN_AT_DEINIT_UNRESOLVED");
   for(int k=0; k<ArraySize(_dxPostActive); k++)
      DxWritePostStop(_dxPostActive[k], "CENSORED_TEST_END");
   ArrayResize(_dxPostActive, 0);
   FileFlush(_dxHandle);
   FileClose(_dxHandle);
   _dxHandle = INVALID_HANDLE;
   if(_dxPostHandle != INVALID_HANDLE)
   {
      FileFlush(_dxPostHandle);
      FileClose(_dxPostHandle);
      _dxPostHandle = INVALID_HANDLE;
   }
   Print(_dxWriteFailed ? "[DX] EVIDENCE INCOMPLETE: review tester logs."
                        : "[DX] CSVs complete: NYAO_ENTRY_DIAGNOSTICS.csv and NYAO_STOP_RECOVERY_TICKS.csv");
}
