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

int _dxHandle = INVALID_HANDLE;
DxTrade _dxActive[];
string _dxPath = "NYAO_ENTRY_DIAGNOSTICS.csv";
bool _dxWriteFailed = false;

bool DxInit()
{
   if(!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))
      return false;
   ArrayResize(_dxActive, 0);
   _dxWriteFailed = false;
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

void DxOnTick()
{
   if(_dxHandle == INVALID_HANDLE || ArraySize(_dxActive) == 0) return;
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;
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
   FileFlush(_dxHandle);
   FileClose(_dxHandle);
   _dxHandle = INVALID_HANDLE;
   Print(_dxWriteFailed ? "[DX] EVIDENCE INCOMPLETE: review tester logs."
                        : "[DX] CSV complete: MetaQuotes\\Terminal\\Common\\Files\\NYAO_ENTRY_DIAGNOSTICS.csv");
}
