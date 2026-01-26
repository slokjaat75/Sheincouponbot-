<?php
// payment_gateway.php - Simplified UPI Payment Gateway with Direct Paytm Integration
error_reporting(0);
header("Content-Type: application/json");
header("Cache-Control: no-store, no-cache, must-revalidate, max-age=0");
header("Pragma: no-cache");
date_default_timezone_set('Asia/Kolkata');

// ================= CONFIGURATION =================
define('DEFAULT_MID', 'wmcSWT27547346044323');
define('DEFAULT_UPI_ID', 'paytmqr5ovnp5@ptys');
define('DEFAULT_PAYMENT_NAME', 'vikash jaat');
define('DB_FILE', 'payments.db');

// ================= DATABASE INITIALIZATION =================
function initDatabase() {
    if (!file_exists(DB_FILE)) {
        $db = new SQLite3(DB_FILE);
        
        // Create payments table only
        $db->exec("CREATE TABLE IF NOT EXISTS payments (
            order_id TEXT PRIMARY KEY,
            amount REAL NOT NULL,
            note TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            mid TEXT NOT NULL,
            upi_id TEXT NOT NULL,
            payment_name TEXT NOT NULL,
            utr TEXT,
            txn_amount REAL,
            last_checked DATETIME,
            checked_count INTEGER DEFAULT 0,
            verified_at DATETIME,
            paytm_response TEXT
        )");
        
        // Create indexes
        $db->exec("CREATE INDEX IF NOT EXISTS idx_payments_mid ON payments(mid)");
        $db->exec("CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)");
        $db->exec("CREATE INDEX IF NOT EXISTS idx_payments_created_at ON payments(created_at)");
        
        $db->close();
    }
}

// Initialize database
initDatabase();

// Get SQLite connection
function getDB() {
    static $db = null;
    if ($db === null) {
        $db = new SQLite3(DB_FILE);
        $db->busyTimeout(3000);
        $db->exec('PRAGMA journal_mode = WAL;');
        $db->exec('PRAGMA synchronous = NORMAL;');
        $db->exec('PRAGMA cache_size = 10000;');
    }
    return $db;
}

// ================= PAYTM STATUS API =================
function callPaytmStatusAPI($mid, $orderId) {
    $payload = json_encode([
        'MID' => $mid,
        'ORDERID' => $orderId
    ]);
    
    $url = 'https://securegw.paytm.in/order/status?JsonData=' . urlencode($payload);
    
    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL => $url,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 3,
        CURLOPT_CONNECTTIMEOUT => 2,
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_SSL_VERIFYHOST => false,
        CURLOPT_FOLLOWLOCATION => true
    ]);
    
    $response = curl_exec($ch);
    curl_close($ch);
    
    if ($response === false) {
        return ['STATUS' => 'API_ERROR', 'RESPMSG' => 'Failed to connect'];
    }
    
    $data = json_decode($response, true);
    return $data ?: ['STATUS' => 'INVALID_RESPONSE'];
}

// ================= MAIN ROUTING =================
$request_uri = strtok($_SERVER['REQUEST_URI'], '?');
$method = $_SERVER['REQUEST_METHOD'];
$queryParams = $_GET;

// Route: Create Payment (Simplified)
if ($request_uri === '/create.php' || $request_uri === '/create') {
    $mid = $queryParams['mid'] ?? DEFAULT_MID;
    $upi_id = $queryParams['upi_id'] ?? DEFAULT_UPI_ID;
    $payment_name = $queryParams['payment_name'] ?? DEFAULT_PAYMENT_NAME;
    $amount = floatval($queryParams['amount'] ?? 0);
    $note = $queryParams['note'] ?? 'Payment';
    
    // Validate amount
    if ($amount <= 0 || $amount > 100000) {
        echo json_encode(['success' => false, 'error' => 'Invalid amount (1-100000)']);
        exit;
    }
    
    // Generate order ID
    $orderId = 'TRXN' . time() . rand(100, 999);
    
    // Create UPI URL
    $upiLink = "upi://pay?pa=" . urlencode($upi_id) . 
               "&pn=" . urlencode($payment_name) . 
               "&am=" . number_format($amount, 2, '.', '') . 
               "&cu=INR&tr=" . $orderId . 
               "&tn=" . urlencode($note);
    
    // QR code
    $qrCode = "https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=" . urlencode($upiLink);
    
    // Save to database
    $db = getDB();
    $stmt = $db->prepare("INSERT INTO payments (order_id, amount, note, mid, upi_id, payment_name) 
                          VALUES (:oid, :amt, :note, :mid, :upi, :name)");
    
    $stmt->bindValue(':oid', $orderId, SQLITE3_TEXT);
    $stmt->bindValue(':amt', $amount, SQLITE3_FLOAT);
    $stmt->bindValue(':note', $note, SQLITE3_TEXT);
    $stmt->bindValue(':mid', $mid, SQLITE3_TEXT);
    $stmt->bindValue(':upi', $upi_id, SQLITE3_TEXT);
    $stmt->bindValue(':name', $payment_name, SQLITE3_TEXT);
    
    if ($stmt->execute()) {
        echo json_encode([
            'success' => true,
            'order_id' => $orderId,
            'amount' => $amount,
            'upi_url' => $upiLink,
            'qr_code' => $qrCode,
            'note' => $note,
            'store_name' => $payment_name
        ]);
    } else {
        echo json_encode(['success' => false, 'error' => 'Database error']);
    }
    exit;
}

// Route: Check Payment (Simplified)
if ($request_uri === '/checkpayment.php' || $request_uri === '/check') {
    $mid = $queryParams['mid'] ?? DEFAULT_MID;
    $orderId = $queryParams['orderid'] ?? '';
    
    if (empty($orderId)) {
        echo json_encode(['success' => false, 'error' => 'Order ID required']);
        exit;
    }
    
    // Check in database first
    $db = getDB();
    $stmt = $db->prepare("SELECT * FROM payments WHERE order_id = :oid AND mid = :mid");
    $stmt->bindValue(':oid', $orderId, SQLITE3_TEXT);
    $stmt->bindValue(':mid', $mid, SQLITE3_TEXT);
    $result = $stmt->execute();
    $payment = $result->fetchArray(SQLITE3_ASSOC);
    
    if (!$payment) {
        echo json_encode(['success' => false, 'error' => 'Order not found']);
        exit;
    }
    
    // Update check count
    $db->exec("UPDATE payments SET checked_count = checked_count + 1, last_checked = CURRENT_TIMESTAMP 
               WHERE order_id = '{$orderId}'");
    
    // If already successful, return
    if ($payment['status'] === 'TXN_SUCCESS') {
        echo json_encode([
            'STATUS' => 'TXN_SUCCESS',
            'ORDERID' => $payment['order_id'],
            'TXNAMOUNT' => $payment['txn_amount'],
            'BANKTXNID' => $payment['utr']
        ]);
        exit;
    }
    
    // Call Paytm API (FAST - 2 seconds timeout)
    $apiResponse = callPaytmStatusAPI($mid, $orderId);
    
    if (isset($apiResponse['STATUS'])) {
        $status = $apiResponse['STATUS'];
        
        if ($status === 'TXN_SUCCESS') {
            // Update database
            $utr = $apiResponse['BANKTXNID'] ?? '';
            $txnAmount = $apiResponse['TXNAMOUNT'] ?? $payment['amount'];
            
            $stmt = $db->prepare("UPDATE payments SET 
                                status = 'TXN_SUCCESS', 
                                utr = :utr, 
                                txn_amount = :amt,
                                verified_at = CURRENT_TIMESTAMP,
                                paytm_response = :resp
                                WHERE order_id = :oid");
            
            $stmt->bindValue(':utr', $utr, SQLITE3_TEXT);
            $stmt->bindValue(':amt', $txnAmount, SQLITE3_FLOAT);
            $stmt->bindValue(':resp', json_encode($apiResponse), SQLITE3_TEXT);
            $stmt->bindValue(':oid', $orderId, SQLITE3_TEXT);
            $stmt->execute();
            
            echo json_encode([
                'STATUS' => 'TXN_SUCCESS',
                'ORDERID' => $orderId,
                'TXNAMOUNT' => $txnAmount,
                'BANKTXNID' => $utr
            ]);
        } elseif ($status === 'PENDING') {
            echo json_encode([
                'STATUS' => 'PENDING',
                'ORDERID' => $orderId,
                'MESSAGE' => 'Payment pending'
            ]);
        } else {
            echo json_encode([
                'STATUS' => $status,
                'ORDERID' => $orderId,
                'MESSAGE' => $apiResponse['RESPMSG'] ?? 'Payment failed'
            ]);
        }
    } else {
        echo json_encode([
            'STATUS' => 'API_ERROR',
            'ORDERID' => $orderId,
            'MESSAGE' => 'Failed to check status'
        ]);
    }
    exit;
}

// Route: Quick Status Check
if ($request_uri === '/status.php' || $request_uri === '/status') {
    $orderId = $queryParams['orderid'] ?? '';
    
    if (empty($orderId)) {
        echo json_encode(['success' => false, 'error' => 'Order ID required']);
        exit;
    }
    
    $db = getDB();
    $stmt = $db->prepare("SELECT * FROM payments WHERE order_id = :oid");
    $stmt->bindValue(':oid', $orderId, SQLITE3_TEXT);
    $result = $stmt->execute();
    $payment = $result->fetchArray(SQLITE3_ASSOC);
    
    if (!$payment) {
        echo json_encode(['success' => false, 'error' => 'Order not found']);
        exit;
    }
    
    echo json_encode([
        'order_id' => $payment['order_id'],
        'amount' => $payment['amount'],
        'status' => $payment['status'],
        'created_at' => $payment['created_at'],
        'verified_at' => $payment['verified_at'],
        'utr' => $payment['utr']
    ]);
    exit;
}

// Route: List Recent Payments
if ($request_uri === '/list.php' || $request_uri === '/list') {
    $db = getDB();
    $stmt = $db->prepare("SELECT order_id, amount, status, created_at, utr FROM payments 
                          ORDER BY created_at DESC LIMIT 50");
    $result = $stmt->execute();
    
    $payments = [];
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $payments[] = $row;
    }
    
    echo json_encode([
        'success' => true,
        'count' => count($payments),
        'payments' => $payments
    ]);
    exit;
}

// Home Route
if ($request_uri === '/' || $request_uri === '/index.php') {
    echo json_encode([
        'service' => 'Vikash Jaat Payment Gateway',
        'merchant_id' => DEFAULT_MID,
        'upi_id' => DEFAULT_UPI_ID,
        'store_name' => DEFAULT_PAYMENT_NAME,
        'endpoints' => [
            'GET /create?amount=X&note=NOTE' => 'Create payment (Uses default MID/UPI)',
            'GET /check?orderid=ORDER_ID' => 'Check payment status',
            'GET /status?orderid=ORDER_ID' => 'Quick status check',
            'GET /list' => 'List recent payments'
        ],
        'note' => 'Default credentials pre-configured'
    ]);
    exit;
}

// 404
http_response_code(404);
echo json_encode(['success' => false, 'error' => 'Endpoint not found']);
?>
