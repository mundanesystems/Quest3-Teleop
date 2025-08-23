using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;
using Unity.WebRTC;

// Helper class for JSON serialization
[System.Serializable]
class SdpMessage
{
    public string sdp;
    public string type;
}

[RequireComponent(typeof(Renderer))]
public class WebRTCReceiver : MonoBehaviour
{
    [Header("WebRTC Server Configuration")]
    [Tooltip("The IP address and port of the Python WebRTC server.")]
    public string serverUrl = "http://192.168.1.100:8080/offer"; // <-- IMPORTANT: Change this to your PC's local IP address!

    [Header("Rendering")]
    [Tooltip("The Renderer component that will display the video.")]
    public Renderer passthroughRenderer;

    private RTCPeerConnection pc;
    private VideoStreamTrack videoStreamTrack;
    private Coroutine connectionCoroutine;

    void Start()
    {
        if (passthroughRenderer == null)
        {
            passthroughRenderer = GetComponent<Renderer>();
        }
        passthroughRenderer.enabled = false;
        StartConnection();
    }

    void OnDestroy()
    {
        StopConnection();
    }

    public void StartConnection()
    {
        if (connectionCoroutine == null)
        {
            Debug.Log("Starting WebRTC Connection...");
            connectionCoroutine = StartCoroutine(WebRTCManager());
        }
    }

    public void StopConnection()
    {
        if (pc != null)
        {
            pc.Close();
            pc = null;
        }

        if (connectionCoroutine != null)
        {
            StopCoroutine(connectionCoroutine);
            connectionCoroutine = null;
        }

        if(passthroughRenderer != null)
        {
            passthroughRenderer.enabled = false;
            passthroughRenderer.material.mainTexture = null;
        }
    }

    private IEnumerator WebRTCManager()
    {
        // The line "yield return StartCoroutine(WebRTC.Initialize());" has been removed.
        // It is no longer needed in recent versions of the Unity WebRTC package.

        var configuration = GetSelectedSdpSemantics();
        pc = new RTCPeerConnection(ref configuration);
        Debug.Log("RTCPeerConnection created.");

        pc.OnTrack = OnTrackHandler;
        pc.OnConnectionStateChange = state => Debug.Log($"WebRTC Connection State: {state}");

        pc.AddTransceiver(TrackKind.Video).Direction = RTCRtpTransceiverDirection.RecvOnly;

        var offerOperation = pc.CreateOffer();
        yield return offerOperation;

        if (offerOperation.IsError)
        {
            Debug.LogError($"Failed to create offer: {offerOperation.Error}");
            StopConnection();
            yield break;
        }

        var offerDesc = offerOperation.Desc;
        yield return pc.SetLocalDescription(ref offerDesc);
        Debug.Log("Local description set. Sending offer to server...");

        yield return StartCoroutine(SendOfferToServer(offerDesc.sdp));
    }

    private RTCConfiguration GetSelectedSdpSemantics()
    {
        RTCConfiguration config = default;
        config.iceServers = new[] { new RTCIceServer { urls = new[] { "stun:stun.l.google.com:19302" } } };
        return config;
    }

    private void OnTrackHandler(RTCTrackEvent e)
    {
        if (e.Track.Kind == TrackKind.Video)
        {
            videoStreamTrack = (VideoStreamTrack)e.Track;
            Debug.Log("Video Track Received! The stream should appear shortly.");
        }
    }

    private IEnumerator SendOfferToServer(string sdp)
    {
        SdpMessage offer = new SdpMessage { sdp = sdp, type = "offer" };
        string jsonBody = JsonUtility.ToJson(offer);
        byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonBody);

        using (var www = new UnityWebRequest(serverUrl, "POST"))
        {
            www.uploadHandler = new UploadHandlerRaw(bodyRaw);
            www.downloadHandler = new DownloadHandlerBuffer();
            www.SetRequestHeader("Content-Type", "application/json");

            yield return www.SendWebRequest();

            if (www.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError($"Error sending offer to server: {www.error}");
                StopConnection();
            }
            else
            {
                Debug.Log("Received answer from server.");
                yield return OnAnswerReceived(www.downloadHandler.text);
            }
        }
    }

    private IEnumerator OnAnswerReceived(string answerJson)
    {
        SdpMessage answer = JsonUtility.FromJson<SdpMessage>(answerJson);
        if (answer == null || string.IsNullOrEmpty(answer.sdp))
        {
            Debug.LogError("Failed to parse SDP answer from server. The JSON was invalid.");
            StopConnection();
            yield break;
        }

        RTCSessionDescription answerDesc = new RTCSessionDescription
        {
            type = RTCSdpType.Answer,
            sdp = answer.sdp
        };

        var setRemoteOp = pc.SetRemoteDescription(ref answerDesc);
        yield return setRemoteOp;

        if (setRemoteOp.IsError)
        {
            Debug.LogError($"Failed to set remote description: {setRemoteOp.Error}");
            StopConnection();
        }
        else
        {
            Debug.Log("Remote description set. WebRTC connection successfully established!");
        }
    }

    void Update()
    {
        if (videoStreamTrack != null && passthroughRenderer.material.mainTexture != videoStreamTrack.Texture)
        {
            passthroughRenderer.material.mainTexture = videoStreamTrack.Texture;
            passthroughRenderer.enabled = true;
            Debug.Log("Successfully assigned WebRTC video texture to the material.");
        }
    }
}