using UnityEngine;
using TMPro;
using System.Net;
using System.Net.Sockets;
using System.Text;

public class GyroscopeReader : MonoBehaviour
{
    public TextMeshProUGUI dataDisplayText;
    public Transform headAnchor;

    private UdpClient udpClient;
    private string pcIPAddress = "192.168.0.196"; // Your computer's IP
    private int port = 9050;

    // --- Rate Limiting ---
    private float sendInterval = 0.05f; // Sends data 20 times per second (1 / 0.05 = 20)
    private float timeSinceLastSend = 0f;

    void Start()
    {
        udpClient = new UdpClient();
    }

    void Update()
    {
        if (headAnchor == null) return;

        // Add up the time since the last frame
        timeSinceLastSend += Time.deltaTime;

        // Only proceed if enough time has passed
        if (timeSinceLastSend >= sendInterval)
        {
            // Reset the timer
            timeSinceLastSend = 0f;

            Quaternion headRotation = headAnchor.rotation;
            Vector3 eulerAngles = headRotation.eulerAngles;

            if (dataDisplayText != null)
            {
                dataDisplayText.text = $"Orientation (Euler):\nPitch: {eulerAngles.x:F1}, Yaw: {eulerAngles.y:F1}";
            }
            
            string dataToSend = $"{eulerAngles.x},{eulerAngles.y}";
            byte[] dataBytes = Encoding.UTF8.GetBytes(dataToSend);
            udpClient.Send(dataBytes, dataBytes.Length, pcIPAddress, port);
        }
    }

    void OnApplicationQuit()
    {
        if (udpClient != null)
        {
            udpClient.Close();
        }
    }
}