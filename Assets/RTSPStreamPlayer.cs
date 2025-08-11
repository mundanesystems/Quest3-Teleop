using UnityEngine;
using UnityEngine.Video; // Required for the VideoPlayer API

[RequireComponent(typeof(VideoPlayer))]
public class RTSPStreamPlayer : MonoBehaviour
{
    [Tooltip("The local IP address of the PC running the Python server.")]
    public string serverAddress = "192.168.0.196";

    [Tooltip("The port specified in the Python server (default is 30000).")]
    public int serverPort = 30000;

    private VideoPlayer videoPlayer;

    void Start()
    {
        // Get the VideoPlayer component attached to this GameObject
        videoPlayer = GetComponent<VideoPlayer>();

        // Construct the RTSP stream URL
        string rtspUrl = $"rtsp://{serverAddress}:{serverPort}/zed";
        Debug.Log($"Attempting to play stream from: {rtspUrl}");

        // Configure the VideoPlayer
        videoPlayer.source = VideoSource.Url;
        videoPlayer.url = rtspUrl;
        videoPlayer.isLooping = true; // Keep trying to connect if it fails

        // Start playing the stream
        videoPlayer.Play();
    }

    void Update()
    {
        // Optional: You can add error checking here if you want
        if (videoPlayer.isPrepared && !videoPlayer.isPlaying)
        {
            Debug.LogWarning("Video is prepared but not playing. Attempting to restart.");
            videoPlayer.Play();
        }
    }
}