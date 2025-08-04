using UnityEngine;
using TMPro;
using System.Net;
using System.Net.Sockets;
using System.Text;

/// <summary>
/// Oculus Link-optimized gyroscope reader for instant VR testing
/// Works in Unity Editor Play mode with Quest 3 via Oculus Link
/// No Android builds needed!
/// </summary>
public class OculusLinkGyroscopeReader : MonoBehaviour
{
    [Header("Network Settings")]
    public string pcIPAddress = "127.0.0.1"; // localhost for Oculus Link
    public int port = 9050;

    [Header("VR Settings")]
    [Tooltip("The main camera/head transform (auto-detected if null)")]
    public Transform headAnchor;
    [Tooltip("Display gyroscope data in VR")]
    public TextMeshProUGUI dataDisplayText;

    [Header("Rate Limiting")]
    [Tooltip("Sends data X times per second")]
    public float sendRate = 20f; // 20 FPS
    
    [Header("Debug Settings")]
    public bool showDebugInfo = true;
    public bool logDataSending = false;

    private UdpClient udpClient;
    private float sendInterval;
    private float timeSinceLastSend = 0f;
    
    // Debug info
    private int packetsSent = 0;
    private float lastDebugTime = 0f;

    void Start()
    {
        // Calculate send interval
        sendInterval = 1f / sendRate;
        
        // Auto-find head anchor if not set
        if (headAnchor == null)
        {
            // Try main camera first
            if (Camera.main != null)
                headAnchor = Camera.main.transform;
            else
            {
                // Try VR center eye anchor
                GameObject centerEye = GameObject.Find("CenterEyeAnchor");
                if (centerEye != null)
                    headAnchor = centerEye.transform;
            }
        }

        // Initialize UDP client
        try
        {
            udpClient = new UdpClient();
            
            if (showDebugInfo)
            {
                Debug.Log("=== OCULUS LINK GYROSCOPE READER STARTED ===");
                Debug.Log($"Sending to: {pcIPAddress}:{port}");
                Debug.Log($"Send rate: {sendRate} Hz");
                Debug.Log("Works in Unity Editor Play mode with Oculus Link!");
                
                if (headAnchor != null)
                    Debug.Log($"✓ Head anchor found: {headAnchor.name}");
                else
                    Debug.LogWarning("⚠ No head anchor found - gyroscope data may not work");
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"Failed to initialize UDP client: {e.Message}");
        }
    }

    void Update()
    {
        if (headAnchor == null || udpClient == null) return;

        // Rate limiting
        timeSinceLastSend += Time.deltaTime;
        if (timeSinceLastSend < sendInterval) return;

        timeSinceLastSend = 0f;

        // Get head rotation
        Quaternion headRotation = headAnchor.rotation;
        Vector3 eulerAngles = headRotation.eulerAngles;

        // Update display text if available
        if (dataDisplayText != null)
        {
            dataDisplayText.text = $"Orientation (Euler):\nPitch: {eulerAngles.x:F1}°\nYaw: {eulerAngles.y:F1}°\nRoll: {eulerAngles.z:F1}°\nMode: Oculus Link";
        }

        // Send gyroscope data
        try
        {
            string dataToSend = $"{eulerAngles.x},{eulerAngles.y}";
            byte[] dataBytes = Encoding.UTF8.GetBytes(dataToSend);
            udpClient.Send(dataBytes, dataBytes.Length, pcIPAddress, port);
            
            packetsSent++;
            
            if (logDataSending && showDebugInfo)
            {
                Debug.Log($"Sent: Pitch={eulerAngles.x:F1}, Yaw={eulerAngles.y:F1}");
            }
        }
        catch (System.Exception e)
        {
            if (showDebugInfo)
                Debug.LogError($"Failed to send gyroscope data: {e.Message}");
        }

        // Debug info every second
        if (showDebugInfo && Time.time - lastDebugTime > 1.0f)
        {
            float actualSendRate = packetsSent / (Time.time - lastDebugTime);
            Debug.Log($"Gyroscope sending at {actualSendRate:F1} Hz | Packets: {packetsSent}");
            packetsSent = 0;
            lastDebugTime = Time.time;
        }
    }

    void OnApplicationQuit()
    {
        if (udpClient != null)
        {
            if (showDebugInfo)
                Debug.Log("Closing gyroscope UDP connection...");
            udpClient.Close();
        }
    }

    void OnDestroy()
    {
        if (udpClient != null)
        {
            udpClient.Close();
        }
    }

    // Public methods for debugging
    public void SetSendRate(float newRate)
    {
        sendRate = Mathf.Clamp(newRate, 1f, 60f);
        sendInterval = 1f / sendRate;
        if (showDebugInfo)
            Debug.Log($"Gyroscope send rate changed to {sendRate} Hz");
    }

    public string GetStatus()
    {
        return $"Connected: {udpClient != null} | Send Rate: {sendRate} Hz | Target: {pcIPAddress}:{port}";
    }
}
