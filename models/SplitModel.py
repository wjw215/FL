import copy

import torch
from torch import nn
import torch.nn.functional as F
import math

from models.resnetcifar import BasicBlock
from models.stein_identity import SteinIdentity


def _make_layer(block, inplanes, planes, stride=1):
    norm_layer = nn.BatchNorm2d
    downsample = None
    if stride != 1 or inplanes != planes:
        downsample = nn.Sequential(
            nn.Conv2d(inplanes, planes, 1, stride, bias=False),
            norm_layer(planes),
        )

    layers = []
    layers.append(block(inplanes, planes, stride, downsample, norm_layer=norm_layer))
    inplanes = planes
    layers.append(block(inplanes, planes, norm_layer=norm_layer))

    return nn.Sequential(*layers)


# Model at client side
class ResNet18_client_side(SteinIdentity):
    def __init__(self, args):
        super(ResNet18_client_side, self).__init__(args=args)
        self.layer1 = nn.Sequential(
            nn.Conv2d(3, 64, kernel_size=3, stride=1, padding=1, bias=False),
            nn.BatchNorm2d(64)
        )
        self.relu = nn.ReLU(inplace=True)
        self.layer2 = _make_layer(BasicBlock, 64, 64, 1)

        # Add additional convolutional layers before FC
        self.conv = nn.Sequential(
            nn.AdaptiveAvgPool2d((2, 2))
        )

        self.fc = nn.Linear(256, 10)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, (nn.BatchNorm2d, nn.GroupNorm)):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def _forward(self, x, label=None):
        # batch_size = input_image.size(0)
        # features = self.encoder(input_image).view(batch_size, -1)
        # cls_result = self.classification(features)
        x = self.layer1(x)
        x = self.relu(x)
        feature = self.layer2(x)
        if label is None:
            return feature

        x = self.conv(feature)
        x = x.view(feature.size(0), -1)
        y = self.fc(x)
        loss = F.cross_entropy(y, label)
        return feature, loss

    def forward(self, input_image, label=None, estimate_grad=False):
        if estimate_grad:
            with torch.no_grad():
                cls_result, loss = self._forward(input_image, label)
            self._stein_estimation(input_image, label, loss)
        else:
            cls_result = self._forward(input_image, label)
        return cls_result


# Model at server side
class ResNet18_server_side(nn.Module):
    def __init__(self):
        super(ResNet18_server_side, self).__init__()
        self.blk2 = _make_layer(BasicBlock, 64, 128, 2)
        self.blk3 = _make_layer(BasicBlock, 128, 256, 2)
        self.blk4 = _make_layer(BasicBlock, 256, 512, 2)
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.outlayer = nn.Linear(512 * 1 * 1, 10)
        # self.blk2 = ResBlk(64, 128, stride=2)
        # self.blk3 = ResBlk(128, 256, stride=2)
        # self.blk4 = ResBlk(256, 512, stride=2)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, (nn.BatchNorm2d, nn.GroupNorm)):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def forward(self, x):
        x = self.blk2(x)
        x = self.blk3(x)
        x = self.blk4(x)
        x = self.avgpool(x)
        x = x.view(x.size(0), -1)
        x = self.outlayer(x)

        return x


class Complete_ResNet18(nn.Module):
    def __init__(self, resNet18_client_side: nn.Module, resNet18_server_side: nn.Module):
        super().__init__()
        self.resNet18_client_side = resNet18_client_side
        self.resNet18_server_side = resNet18_server_side

    def forward(self, x):
        result = {}
        x = self.resNet18_client_side(x)
        x = self.resNet18_server_side(x)
        result['output'] = x
        return result


class VGG16_client_side(nn.Module):

    def __init__(self):
        super(VGG16_client_side, self).__init__()
        self.layer1 = nn.Sequential(nn.Conv2d(3, 64, 3, 1, 1), nn.BatchNorm2d(64), nn.ReLU(),
                                    nn.Conv2d(64, 64, 3, 1, 1), nn.BatchNorm2d(64), nn.ReLU(), nn.MaxPool2d(2, 2))
        self.layer2 = nn.Sequential(nn.Conv2d(64, 128, 3, 1, 1), nn.BatchNorm2d(128), nn.ReLU(),
                                    nn.Conv2d(128, 128, 3, 1, 1), nn.BatchNorm2d(128), nn.ReLU(), nn.MaxPool2d(2, 2))

    def forward(self, x):
        x = self.layer1(x)
        x = self.layer2(x)
        return x


class VGG16_server_side(nn.Module):

    def __init__(self):
        super(VGG16_server_side, self).__init__()
        self.layer3 = nn.Sequential(nn.Conv2d(128, 256, 3, 1, 1), nn.BatchNorm2d(256), nn.ReLU(),
                                    nn.Conv2d(256, 256, 3, 1, 1), nn.BatchNorm2d(256), nn.ReLU(),
                                    nn.Conv2d(256, 256, 3, 1, 1), nn.BatchNorm2d(256), nn.ReLU(), nn.MaxPool2d(2, 2))
        self.layer4 = nn.Sequential(nn.Conv2d(256, 512, 3, 1, 1), nn.BatchNorm2d(512), nn.ReLU(),
                                    nn.Conv2d(512, 512, 3, 1, 1), nn.BatchNorm2d(512), nn.ReLU(),
                                    nn.Conv2d(512, 512, 3, 1, 1), nn.BatchNorm2d(512), nn.ReLU(), nn.MaxPool2d(2, 2))
        self.layer5 = nn.Sequential(nn.Conv2d(512, 512, 3, 1, 1), nn.BatchNorm2d(512), nn.ReLU(),
                                    nn.Conv2d(512, 512, 3, 1, 1), nn.BatchNorm2d(512), nn.ReLU(),
                                    nn.Conv2d(512, 512, 3, 1, 1), nn.BatchNorm2d(512), nn.ReLU(), nn.MaxPool2d(2, 2))
        self.fc1 = nn.Sequential(nn.Flatten(), nn.Linear(512, 512), nn.ReLU(), nn.Dropout())
        self.fc2 = nn.Sequential(nn.Linear(512, 256), nn.ReLU(), nn.Dropout())
        self.fc3 = nn.Linear(256, 10)

    def forward(self, x):
        x = self.layer3(x)
        x = self.layer4(x)
        x = self.layer5(x)
        x = self.fc1(x)
        x = self.fc2(x)
        x = self.fc3(x)
        return x
