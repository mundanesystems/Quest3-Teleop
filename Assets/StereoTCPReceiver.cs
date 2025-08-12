using UnityEngine;
using System;
using System.IO;
using System.Net.Sockets;
using System.Threading;
using System.Diagnostics; // Required for Stopwatch
using SixLabors.ImageSharp;
using SixLabors.ImageSharp.PixelFormats;

// Renamed for clarity
public class LatencyTestReceiver : MonoBehaviour
{
    [Header("Network Settings")]
    public string serverAddress = "192.168.0.196";
    public int serverPort = 8080;

    [Header("Display Settings")]
    public float screenDistance = 1.0f;

    // A class to hold all the data passed between threads
    private class FrameData
    {
        public byte[] RawPixelData;
        public int ImageWidth;
        public int ImageHeight;
        public float SendReceiveLatencyMs;
        public float DecompressionLatencyMs;
        public double DecompressionFinishTime;
    }

    private Thread clientThread;
    private bool isRunning = false;
    
    private Texture2D videoTexture;
    private readonly object dataLock = new object();
    private FrameData latestFrameData;
    private bool newFrameReady = false;
    private float hFovDegrees = -1;
    
    // For logging periodically
    private int frameCount = 0;
    private const int LOG_INTERVAL = 60; // Log every 60 frames

    void Start()
    {
        videoTexture = new Texture2D(2, 2, TextureFormat.RGBA32, false, true);
        GetComponent<Renderer>().material.mainTexture = videoTexture;
        isRunning = true;
        clientThread = new Thread(NetworkLoop);
        clientThread.IsBackground = true;
        clientThread.Start();
    }

    private void NetworkLoop()
    {
        try
        {
            using (var client = new TcpClient(serverAddress, serverPort))
            using (var stream = client.GetStream())
            {
                UnityEngine.Debug.Log("✅ [Latency Test] Connected to server.");
                
                // Read FOV data
                string[] fovs = System.Text.Encoding.UTF8.GetString(ReadExactly(stream, BitConverter.ToInt32(ReadExactly(stream, 4), 0))).Split(',');
                hFovDegrees = float.Parse(fovs[0]);

                var stopwatch = new Stopwatch();

                while (isRunning)
                {
                    // --- 1. Read Timestamp and calculate Send/Receive latency ---
                    byte[] timestampBytes = ReadExactly(stream, 8);
                    double sendTimestamp = BitConverter.ToDouble(timestampBytes, 0);
                    double receiveTimestamp = (DateTime.UtcNow - new DateTime(1970, 1, 1)).TotalSeconds;
                    float sendReceiveLatency = (float)(receiveTimestamp - sendTimestamp) * 1000f; // in milliseconds

                    // --- 2. Read frame and time the JPEG decompression ---
                    byte[] frameJpegData = ReadExactly(stream, BitConverter.ToInt32(ReadExactly(stream, 4), 0));
                    
                    stopwatch.Restart();
                    using (Image<Rgba32> image = Image.Load<Rgba32>(frameJpegData))
                    {
                        stopwatch.Stop();
                        float decompLatency = stopwatch.ElapsedMilliseconds;
                        
                        // Record the time immediately after decompression
                        double decompFinishTime = Time.realtimeSinceStartupAsDouble;

                        lock (dataLock)
                        {
                            latestFrameData = new FrameData
                            {
                                RawPixelData = new byte[image.Width * image.Height * 4],
                                ImageWidth = image.Width,
                                ImageHeight = image.Height,
                                SendReceiveLatencyMs = sendReceiveLatency,
                                DecompressionLatencyMs = decompLatency,
                                DecompressionFinishTime = decompFinishTime
                            };
                            image.CopyPixelDataTo(latestFrameData.RawPixelData);
                            newFrameReady = true;
                        }
                    }
                }
            }
        }
        catch (Exception e)
        {
            UnityEngine.Debug.LogError($"[Latency Test] Network error: {e.Message}");
            isRunning = false;
        }
    }

    private byte[] ReadExactly(NetworkStream stream, int size)
    {
        byte[] buffer = new byte[size];
        int offset = 0;
        while (offset < size)
        {
            int read = stream.Read(buffer, offset, size - offset);
            if (read == 0) throw new EndOfStreamException("Stream closed unexpectedly.");
            offset += read;
        }
        return buffer;
    }

    void Update()
    {
        if (hFovDegrees > 0)
        {
            float hFovRad = hFovDegrees * Mathf.Deg2Rad;
            float quadWidth = 2.0f * screenDistance * Mathf.Tan(hFovRad * 0.5f);
            float vFovRad = Camera.main.fieldOfView * Mathf.Deg2Rad;
            float quadHeight = 2.0f * screenDistance * Mathf.Tan(vFovRad * 0.5f);
            transform.localScale = new Vector3(quadWidth, quadHeight, 1);
            hFovDegrees = -1;
        }

        if (newFrameReady)
        {
            FrameData currentFrame;
            lock (dataLock)
            {
                currentFrame = latestFrameData;
                newFrameReady = false;
            }
            
            if (videoTexture.width != currentFrame.ImageWidth || videoTexture.height != currentFrame.ImageHeight)
            {
                videoTexture.Reinitialize(currentFrame.ImageWidth, currentFrame.ImageHeight);
            }
            videoTexture.LoadRawTextureData(currentFrame.RawPixelData);
            videoTexture.Apply();

            // --- 3. Calculate Decomp to Display latency and Log ---
            float decompToDisplayLatency = (float)(Time.realtimeSinceStartupAsDouble - currentFrame.DecompressionFinishTime) * 1000f;

            frameCount++;
            if (frameCount % LOG_INTERVAL == 0)
            {
                UnityEngine.Debug.Log(
                    $"--- Latency Report (Frame {frameCount}) ---\n" +
                    $"Send/Receive: {currentFrame.SendReceiveLatencyMs:F2} ms\n" +
                    $"JPEG Decomp: {currentFrame.DecompressionLatencyMs:F2} ms\n" +
                    $"Decomp to Display: {decompToDisplayLatency:F2} ms"
                );
            }
        }
    }

    void OnDestroy()
    {
        isRunning = false;
        if (clientThread != null && clientThread.IsAlive) clientThread.Abort();
    }
}