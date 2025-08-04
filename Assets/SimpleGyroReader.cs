using UnityEngine;
using System.Net;
using System.Net.Sockets;
using System.Text;

/// <summary>
/// Simple gyroscope reader - minimal version that should compile without issues
/// </summary>
public class SimpleGyroReader : MonoBehaviour
{
    public string pcIPAddress = "127.0.0.1";
    public int port = 9050;
    public Transform headAnchor;
    
    private UdpClient udpClient;
    private float sendInterval = 0.05f; // 20 FPS
    private float timeSinceLastSend = 0f;

    void Start()
    {
        Debug.Log("=== SIMPLE GYROSCOPE READER STARTED ===");
        
        udpClient = new UdpClient();
        
        // Find head anchor if not set
        if (headAnchor == null)
        {
            if (Camera.main != null)
                headAnchor = Camera.main.transform;
        }
        
        Debug.Log($"Sending gyroscope data to {pcIPAddress}:{port}");
    }

    void Update()
    {
        if (headAnchor == null) return;

        timeSinceLastSend += Time.deltaTime;
        if (timeSinceLastSend < sendInterval) return;

        timeSinceLastSend = 0f;

        // Get head rotation
        Vector3 eulerAngles = headAnchor.rotation.eulerAngles;
        
        // Send data
        try
        {
            string dataToSend = $"{eulerAngles.x},{eulerAngles.y}";
            byte[] dataBytes = Encoding.UTF8.GetBytes(dataToSend);
            udpClient.Send(dataBytes, dataBytes.Length, pcIPAddress, port);
        }
        catch (System.Exception e)
        {
            Debug.LogError($"Error sending gyroscope data: {e.Message}");
        }
    }

    void OnDestroy()
    {
        if (udpClient != null)
            udpClient.Close();
    }
}
