import torch
import torch.optim as optim
import torch.nn as nn
from torch.autograd import grad
import matplotlib.pyplot as plt
from torch.autograd import Variable
import time as t
import torch.nn.functional as F


###### DISCRIMINATOR NETWORK 
# D(x) is the discriminator network which outputs the (scalar) probability that x
# came from training data rather than the generator. Here, sinum_channele we are dealing with 
# images, the input to D(x) is an image.

class DCGANDiscriminator(nn.Module):
    def __init__(self, img_size, dim):
        """
        img_size : (int, int, int)
            img_size[0] : num_channels (e.g. 3 for RGB, 1 for grayscale)
            img_size[1] : Height (H)
            img_size[2] : Width (W)
        """
        super(DCGANDiscriminator, self).__init__()

        self.img_size = img_size

        self.image_to_features = nn.Sequential(
            nn.Conv2d(self.img_size[0], dim, 4, 2, 1),  # First dimension is the number of channels
            nn.LeakyReLU(0.2),
            nn.Conv2d(dim, 2 * dim, 4, 2, 1),
            nn.LeakyReLU(0.2),
            nn.Conv2d(2 * dim, 4 * dim, 4, 2, 1),
            nn.LeakyReLU(0.2),
            nn.Conv2d(4 * dim, 8 * dim, 4, 2, 1),
            nn.Sigmoid()
        )

        # Output size calculation after 4 convolutions with stride 2 (halving size each time)
        output_size = 8 * dim * (img_size[1] // 16) * (img_size[2] // 16)
        self.features_to_prob = nn.Sequential(
            nn.Linear(output_size, 1),
            nn.Sigmoid()
        )

    def forward(self, input_data):
        batch_size = input_data.size()[0]
        x = self.image_to_features(input_data)
        x = x.view(batch_size, -1)
        return self.features_to_prob(x)
 
    
###### GENERATOR NETWORK
# For the generator’s notation, let z be a latent space vector sampled from a standard normal 
# distribution. G(z) represents the generator funum_channeltion which maps the latent vector z to data-space. 
# The goal of G is to estimate the distribution that the training data comes from (p_data) so it 
# can generate fake samples from that estimated distribution (p_g).

class DCGANGenerator(nn.Module):
    def __init__(self, img_size, latent_dim, dim):
        super(DCGANGenerator, self).__init__()

        self.dim = dim
        self.latent_dim = latent_dim
        self.img_size = img_size
        self.feature_sizes = (self.img_size[1] // 16, self.img_size[2] // 16)  # Adjusted for (height, width)

        self.latent_to_features = nn.Sequential(
            nn.Linear(latent_dim, 8 * dim * self.feature_sizes[0] * self.feature_sizes[1]),
            nn.ReLU()
        )

        self.features_to_image = nn.Sequential(
            nn.ConvTranspose2d(8 * dim, 4 * dim, 4, 2, 1),
            nn.ReLU(),
            nn.BatchNorm2d(4 * dim),
            nn.ConvTranspose2d(4 * dim, 2 * dim, 4, 2, 1),
            nn.ReLU(),
            nn.BatchNorm2d(2 * dim),
            nn.ConvTranspose2d(2 * dim, dim, 4, 2, 1),
            nn.ReLU(),
            nn.BatchNorm2d(dim),
            nn.ConvTranspose2d(dim, self.img_size[0], 4, 2, 1),  # Adjusted for output channels
            nn.Sigmoid()
        )

    def forward(self, input_data):
        # Map latent vector to appropriate size for transposed convolutions
        x = self.latent_to_features(input_data)
        # Reshape to (batch_size, 8 * dim, feature_height, feature_width)
        x = x.view(-1, 8 * self.dim, self.feature_sizes[0], self.feature_sizes[1])
        # Return the generated image
        return self.features_to_image(x)

    def init_weight(self, num_samples):
        return torch.randn((num_samples, self.latent_dim))

class DCGAN_Trainer(object):
    def __init__(self, opt, dataloader):
        """
        Args:
            discriminator: The discriminator model.
            generator: The generator model.
            dataloader: The dataloader for training data.
            lr: Learning rate.
            beta1: Beta1 parameter for Adam optimizer.
           beta2: Beta2 parameter for Adam optimizer.
            mode: "normal" or "wasserstein" to choose the training type.
            lambda_gp: Coefficient for gradient penalty in WGAN-GP.
        """
        self.discriminator = DCGANDiscriminator(opt["img_size"], opt["dim"])
        self.generator = DCGANGenerator(opt["img_size"], opt["latent_dim"], opt["dim"])
        self.dataloader = dataloader
        # store accuracies and losses for plotting
        self.D_loss, self.G_loss, self.gradient_penalty_list = [], [], []
        self.epoch_times = []
        self.lr = opt["lr"]
        self.beta1 = opt["beta1"]
        self.beta2 = opt["beta2"]
        self.device = opt["device"]
        self.criterion = nn.BCELoss()
        self.batch_size = opt["batch_size"] 
        # Optimizers for discriminator and generator
        self.optimizer_D = optim.Adam(self.discriminator.parameters(), lr=self.lr, betas=(self.beta1, self.beta2))
        self.optimizer_G = optim.Adam(self.generator.parameters(), lr=self.lr, betas=(self.beta1, self.beta2))

        self.criterion = nn.BCELoss().to(self.device)

        self.num_epochs = opt["num_epochs"]

    def train(self):
        """
        Main training loop for the GAN, including discriminator accuracy calculation.

        Args:
            num_epochs: Number of training epochs.
            device: Device to run the training on (e.g., "cuda" or "cpu").
            save_path_generator: Path to save the trained generator model.
            save_path_discriminator: Path to save the trained discriminator model.
        """
        self.discriminator.to(self.device)
        self.generator.to(self.device)
        # we want to compare the rapidity of the training
        total_time_start = t.time()

        for epoch in range(self.num_epochs):
            start_time = t.time()
            epoch_discriminator_loss = 0
            epoch_generator_loss = 0


            for i, (real_data, _) in enumerate(self.dataloader):
                real_data = real_data.to(self.device)

                z = torch.randn((self.batch_size, self.generator.latent_dim))
                real_labels = torch.ones(self.batch_size)
                fake_labels = torch.zeros(self.batch_size)

                images, z = Variable(images).to(self.device), Variable(z).to(self.device)
                real_labels, fake_labels = Variable(real_labels).to(self.device), Variable(fake_labels).to(self.device)

                #####################################################################################
                ################################ TRAIN DISCRIMINATOR ################################
                #####################################################################################

                outputs = self.discriminator(images)
                d_loss_real = self.loss(outputs.flatten(), real_labels)
                real_score = outputs

                fake_images = self.generator(z)
                outputs = self.discriminator(fake_images)
                d_loss_fake = self.D_loss(outputs.flatten(), fake_labels)
                fake_score = outputs

                # Optimize discriminator
                d_loss = d_loss_real + d_loss_fake
                self.discriminator.zero_grad()
                d_loss.backward()
                self.optimizer_D.step()

                #####################################################################################
                ################################## TRAIN GENERATOR ##################################
                #####################################################################################
                z = torch.randn((self.batch_size, self.generator.latent_dim))
                fake_images = self.generator(z)
                outputs = self.discriminator(fake_images)
                g_loss = self.G_loss(outputs.flatten(), real_labels)

                self.discriminator.zero_grad()
                self.generator.zero_grad()
                g_loss.backward()
                self.optimizer_G.step()

                # Print loss and accuracy every 50 iterations
                if i % 50 == 0:
                    print('[%d/%d][%d/%d]\tLoss_D: %.4f\tLoss_G: %.4f'
                        % (epoch + 1, self.num_epochs, i, len(self.dataloader), d_loss, g_loss))

            # save the time taken by the epoch
            self.epoch_times.append(t.time() - start_time)

            # save the losses values at the end of each epoch
            avg_discriminator_loss = epoch_discriminator_loss / len(self.dataloader)
            avg_generator_loss = epoch_generator_loss / len(self.dataloader)
            self.G_loss.append(avg_generator_loss)
            self.D_loss.append(avg_discriminator_loss)

        total_time_end = t.time()
        self.training_time = total_time_end - total_time_start
        print('Time of training-{}'.format((self.training_time)))

        save_path_generator=f"../trained_models/DCGANgenerator_epoch{self.num_epochs}.pth"
        save_path_discriminator=f"../trained_models/DCGANdiscriminator_epoch{self.num_epochs}.pth"
        # Save the trained models
        torch.save(self.generator.state_dict(), save_path_generator)
        torch.save(self.discriminator.state_dict(), save_path_discriminator)
        print(f"Models saved: Generator -> {save_path_generator}, Discriminator -> {save_path_discriminator}")

        # Plot the generator and discriminator losses
        plt.figure(figsize=(10, 5))
        plt.title("Generator and Discriminator Loss During Training")
        plt.plot(self.G_loss, label="G")
        plt.plot(self.D_loss, label="D")
        plt.xlabel("Iterations")
        plt.ylabel("Loss")
        plt.legend()
        plt.show()

        return self.G_loss, self.D_loss, self.epoch_times, self.training_time
    
# Exemple d'utilisation :
# trainer = Trainer(discriminator, generator, dataloader, lr=0.0002, beta1=0.5, beta2=0.999, mode="wasserstein")
# trainer.train(num_epochs=100, device=torch.device("cuda" if torch.cuda.is_available() else "cpu"))
