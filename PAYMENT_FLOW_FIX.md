# Payment Callback Flow - Bug Fix Summary

## Problem Identified
The payment processing flow was incorrectly treating the initial Orchard API response (resp_code "015") as final success, immediately confirming to the user that the payment was completed. However, response code "015" only means "Request successfully received for processing" - the actual payment result comes later via a callback webhook.

### Previous Behavior (INCORRECT):
```
1. User sends payment request via WhatsApp
2. → NLU processes intent
3. → Payment Service sends to Orchard API
4. → Gets resp_code "015" (request received)
5. ❌ IMMEDIATELY marks as SUCCESS
6. ❌ IMMEDIATELY sends success confirmation to user
7. Later... Orchard sends callback (trans_status: 000 for success, 001 for failure)
8. ⚠️ If callback indicates failure, user was already told it succeeded!
```

## Solutions Implemented

### 1. **Updated Payment Service** (`src/core/payments/service/paymentservice.py`)

#### Changed Response Handling (Lines 106-120):
- **Before**: Response code "015" was treated as SUCCESS
- **After**: Response code "015" is treated as PENDING (awaiting callback)
- Created new method `_handle_pending_payment()` to set status to PENDING instead of SUCCESS

```python
# NEW CODE:
if response_data and response_data.get("resp_code") == "015":
    # 015 = "Request successfully received for processing"
    # This is NOT final success - we must wait for the callback to confirm
    logger.info(f"Payment request accepted for processing...")
    return self._handle_pending_payment(payment, response_data)
```

#### Updated Callback Handler (Lines 122-162):
- Modified `process_payment_callback()` to properly handle final payment status
- When callback arrives with `trans_status: 000` (success), it now:
  - Calls `_handle_success()` to create invoice
  - Updates payment status to SUCCESS
  - Persists the final state to database

### 2. **Updated NLU System** (`src/core/nlu/nlu.py`)

#### Enhanced Payment Response Logic (Lines 297-305):
- **PENDING Status**: Returns the standard success message (callback will update user later)
- **SUCCESS Status**: Returns the confirmation message (after callback confirms)
- **FAILED Status**: Returns error message

```python
# UPDATED FLOW:
if result.status == PaymentStatus.PENDING:
    message = self._get_success_message(intent, slots, result)
    return self.response_formatter.format_response(intent, "success", message=message)
elif result.status == PaymentStatus.SUCCESS:
    message = self._get_success_message(intent, slots, result)
    return self.response_formatter.format_response(intent, "success", message=message)
```

### 3. **Added Payment Status Endpoint** (`src/core/payments/controller/paymentcontroller.py`)

New endpoint at line 129: `GET /api/v1/payment/status/{transaction_id}`

Allows users to check their payment status:
```bash
GET /api/v1/payment/status/3279794601492687569

Response:
{
  "transaction_id": "3279794601492687569",
  "payment_id": 4,
  "status": "PENDING",  // or SUCCESS, FAILED
  "amount": 0.30,
  "payment_method": "MOBILE_MONEY",
  "created_at": "2025-11-17T10:16:34",
  "updated_at": "2025-11-17T10:16:35"
}
```

## New Payment Flow (CORRECT)

```
1. User sends payment request via WhatsApp
   ↓
2. → NLU processes intent → Payment Service
   ↓
3. → Payment Service sends to Orchard API
   ↓
4. → Gets resp_code "015" (request received)
   ↓
5. ✅ Sets status to PENDING
   ↓
6. ✅ Sends confirmation message to user
   ↓
7. → Orchard API processes payment asynchronously
   ↓
8. → Orchard sends callback webhook with final status (000/001)
   ↓
9. ✅ Callback handler updates payment status (SUCCESS/FAILED)
   ✅ Creates invoice (on success)
   ✅ If needed, sends follow-up notification to user
```

## Status Codes Reference

| Code | Meaning | Payment Status | Action |
|------|---------|---|---|
| 015 | Request received for processing | PENDING | Wait for callback |
| 000 | Transaction successful | SUCCESS | Create invoice, confirm to user |
| 001 | Transaction failed | FAILED | Notify user of failure |

## Testing the Fix

### Scenario 1: Successful Payment
```
1. User: "Send 0.3 cedis to 0550748724"
2. System: "✅ Successfully sent GHS 0.3 to 0550748724. [Transaction ID: xxx]"
3. Payment status: PENDING (awaiting callback)
4. (After Orchard processes and sends callback)
5. Payment status updates to: SUCCESS
```

### Scenario 2: Failed Payment
```
1. User: "Send 0.3 cedis to 0550748724"
2. System: "✅ Successfully sent GHS 0.3 to 0550748724. [Transaction ID: xxx]"
3. Payment status: PENDING (awaiting callback)
4. (After Orchard processes and sends callback with failure)
5. Payment status updates to: FAILED
```

### Scenario 3: User Checking Status
```
User calls: GET /api/v1/payment/status/3279794601492687569
Response: { "status": "PENDING" ... }  // Then later: { "status": "SUCCESS" ... }
```

## Files Modified

1. **src/core/payments/service/paymentservice.py**
   - `_process_gateway_response()` - Updated to handle 015 as PENDING
   - `_handle_pending_payment()` - NEW method for PENDING status
   - `process_payment_callback()` - Enhanced callback handling

2. **src/core/nlu/nlu.py**
   - `_process_payment_intent()` - Updated status handling logic

3. **src/core/payments/controller/paymentcontroller.py**
   - `get_payment_status()` - NEW endpoint for checking transaction status

## Important Notes

- Existing payments already in the database will continue to work
- The callback handler at `/api/v1/payments/callback` must be properly configured in Orchard API settings
- Users can now check their transaction status anytime using the new endpoint
- The user sees the success message immediately, but the payment status remains PENDING until the callback confirms
