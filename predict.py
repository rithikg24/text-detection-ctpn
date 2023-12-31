# Import necessary libraries
import os
import cv2
import numpy as np
import torch
import torch.nn.functional as F
from ctpn import config
from ctpn.ctpn import CTPN_Model
from ctpn.utils import gen_anchor, transform_bbox, clip_bbox, filter_bbox, nms, TextProposalConnectorOriented

# Check if GPU is available, otherwise use CPU
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Loading pre-trained model
weights = './weights/ctpn.pth'
model = CTPN_Model().to(device)
model.load_state_dict(torch.load(weights, map_location=device)['model_state_dict'])
model.eval()

# Function to detect text boxes
def get_text_boxes(image, display=True, prob_thresh=0.4):
    # Get image dimensions
    h, w = image.shape[:2]
    
    # Resize the image
    rescale_fac = max(h, w) / 1000
    if rescale_fac > 1.0:
        h = int(h / rescale_fac)
        w = int(w / rescale_fac)
        image = cv2.resize(image, (w, h))
    
    # Create a copy of the image for visualization
    image_c = image.copy()
    
    # Normalizing the image
    image = image.astype(np.float32) - config.IMAGE_MEAN
    image = torch.from_numpy(image.transpose(2, 0, 1)).unsqueeze(0).float().to(device)
    
    with torch.no_grad():
        # Pass the image to the model
        cls, regr = model(image)                            # return classification scores and reg values
        cls_prob = F.softmax(cls, dim=-1).cpu().numpy()     # gets the probabilites by applying softmax on classification values
        regr = regr.cpu().numpy()
        
        # Generate anchor boxes and transform them
        anchor = gen_anchor((int(h / 16), int(w / 16)), 16)
        bbox = transform_bbox(anchor, regr)
        bbox = clip_bbox(bbox, [h, w])

        # Filter anchor boxes based on probability threshold
        fg = np.where(cls_prob[0, :, 1] > prob_thresh)[0]
        select_anchor = bbox[fg, :]
        select_score = cls_prob[0, fg, 1]
        select_anchor = select_anchor.astype(np.int32)

        # Filter anchor boxes using another threshold
        keep_index = filter_bbox(select_anchor, 16)
        select_anchor = select_anchor[keep_index]
        select_score = select_score[keep_index]
        select_score = np.reshape(select_score, (select_score.shape[0], 1))

        # Apply Non-Maximum Suppression
        nmsbox = np.hstack((select_anchor, select_score))
        keep = nms(nmsbox, 0.3)
        select_anchor = select_anchor[keep]
        select_score = select_score[keep]

        # Use the TextProposalConnectorOriented class to connect text lines
        textConn = TextProposalConnectorOriented()
        text = textConn.get_text_lines(select_anchor, select_score, [h, w])
        
        # Draw bounding boxes and annotations on the image
        if display:
            for i in text:
                i = [int(j) for j in i]
                cv2.line(image_c, (i[0], i[1]), (i[2], i[3]), (0, 0, 255), 2)
                cv2.line(image_c, (i[0], i[1]), (i[4], i[5]), (0, 0, 255), 2)
                cv2.line(image_c, (i[6], i[7]), (i[2], i[3]), (0, 0, 255), 2)
                cv2.line(image_c, (i[4], i[5]), (i[6], i[7]), (0, 0, 255), 2)
        
        # Return detected text lines and the image with bounding boxes
        return text, image_c


# Load the input image
img_path = 'images/download.jpeg'
input_img = cv2.imread(img_path)

# Get detected text lines and image with bounding boxes
text, out_img = get_text_boxes(input_img)

# Save the image with drawn bounding boxes
cv2.imwrite('res.jpg', out_img)